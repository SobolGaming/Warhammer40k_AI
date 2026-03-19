from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class SpaceMarinesStratagemMixin:
    @staticmethod
    def _sm_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _sm_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    def _sm_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "space_marines_detachments", None)

    def _is_saga_of_the_beastslayer_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_saga_of_the_beastslayer", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_1st_company_task_force_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_1st_company_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_vindication_task_force_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_vindication_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _sm_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _sm_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_alive", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _sm_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    def _sm_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._sm_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_adeptus_astartes_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "attached_unit_is_adeptus_astartes", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any("ADEPTUS ASTARTES"))
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "SM"

    @staticmethod
    def _sm_is_thunderwolf_cavalry(unit: Any) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("THUNDERWOLF CAVALRY")):
            return True
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("THUNDERWOLF CAVALRY")):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "thunderwolf cavalry" in name

    @staticmethod
    def _sm_is_terminator_unit(unit: Any) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("TERMINATOR")):
            return True
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("TERMINATOR")):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "terminator" in name

    @staticmethod
    def _sm_is_first_company_veteran_unit(unit: Any) -> bool:
        if unit is None:
            return False
        if SpaceMarinesStratagemMixin._sm_is_terminator_unit(unit):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return any(
            token in name
            for token in (
                "bladeguard veteran squad",
                "sternguard veteran squad",
                "vanguard veteran squad",
            )
        )

    @staticmethod
    def _sm_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _sm_selected_to_charge_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "attempted_charge_this_round", False))

    @staticmethod
    def _sm_selected_to_shoot_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "shot_this_round", False))

    @staticmethod
    def _sm_clear_ability_cache(root: Any, *keys: str) -> None:
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            return
        for key in list(keys or []):
            cache.pop(str(key), None)

    @staticmethod
    def _sm_effective_cp_cost(player: Any, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost) or cp_cost)
        return int(cp_cost)

    @staticmethod
    def _sm_spend_cp(player: Any, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = SpaceMarinesStratagemMixin._sm_effective_cp_cost(player, stratagem, target_unit=target_unit)
        return bool(
            player.spend_command_points(
                int(cp_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _sm_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)

    def _sm_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        target_unit: Any = None,
        attacking_unit: Any = None,
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
            if attacking_unit is not None and reaction.get("attacking_unit") is not attacking_unit:
                continue
            return True
        return False

    def _sm_game_map(self) -> Any:
        return getattr(self.game, "map", None) if self.game is not None else None

    def _sm_objective_candidates_you_control(self, unit: Any) -> list[Any]:
        root = self._sm_root(unit)
        game_map = self._sm_game_map()
        if root is None or game_map is None:
            return []
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if not bool(is_within(loc)):
                continue
            controller = getattr(loc, "controlling_player", None)
            sticky_controller = getattr(loc, "sticky_controller", None)
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

    def _sm_unit_is_engaged(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        game_map = self._sm_game_map()
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._sm_root(enemy)
            if enemy_root is None:
                continue
            if not self._sm_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            try:
                if bool(is_within_engagement(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _sm_next_owner_movement_phase_turn(self, owner: Any) -> int:
        game = self.game
        if game is None or owner is None:
            return int(getattr(game, "turn", 0) or 0) if game is not None else 0
        current_turn = int(getattr(game, "turn", 0) or 0)
        players = list(getattr(game, "players", []) or [])
        starting_index = getattr(game, "battle_round_starting_player_index", None)
        if starting_index is None and players:
            starting_index = 0
        try:
            owner_index = int(players.index(owner))
        except ValueError:
            owner_index = None
        try:
            starting_index = int(starting_index) if starting_index is not None else None
        except (TypeError, ValueError):
            starting_index = None
        if owner_index is not None and starting_index is not None and owner_index == starting_index:
            return int(current_turn + 1)
        return int(current_turn)

    def _sm_next_enemy_command_phase_turn(self) -> tuple[int, str]:
        game = self.game
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        if game is None:
            return (current_turn, "")
        players = list(getattr(game, "players", []) or [])
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is None or len(players) < 2:
            return (current_turn, "")
        try:
            active_index = int(players.index(active_player))
        except ValueError:
            active_index = None
        if active_index is None:
            return (current_turn, "")
        enemy_index = (active_index + 1) % len(players)
        enemy_player = players[enemy_index]
        enemy_id = str(getattr(enemy_player, "id", "") or "")
        starting_index = getattr(game, "battle_round_starting_player_index", None)
        if starting_index is None and players:
            starting_index = 0
        try:
            starting_index = int(starting_index) if starting_index is not None else None
        except (TypeError, ValueError):
            starting_index = None
        due_turn = int(current_turn)
        if starting_index is not None and enemy_index == int(starting_index):
            due_turn = int(current_turn + 1)
        return (due_turn, enemy_id)

    def _sm_clear_terrifying_proficiency_pending(self, root: Any) -> None:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "space_marines_terrifying_proficiency_pending",
            "space_marines_terrifying_proficiency_due_turn",
            "space_marines_terrifying_proficiency_due_player_id",
            "space_marines_terrifying_proficiency_source",
            "space_marines_terrifying_proficiency_turn_owner",
            "space_marines_terrifying_proficiency_turn",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _space_marines_first_company_duty_and_honour_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_1st_company_task_force_detachment():
            return ([], {})
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return ([], {})
        candidates: list[Any] = []
        objective_map: dict[str, list[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if not self._sm_is_first_company_veteran_unit(root):
                continue
            objectives = self._sm_objective_candidates_you_control(root)
            if not objectives:
                continue
            candidates.append(root)
            if uid:
                objective_map[uid] = list(objectives)
        return (sorted(candidates, key=self._sm_sort_key), objective_map)

    def _space_marines_first_company_heroes_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_1st_company_task_force_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        phase_key = str(phase_name or "").strip().lower()
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if not self._sm_is_first_company_veteran_unit(root):
                continue
            if phase_key == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
                continue
            if phase_key == "fight phase" and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_first_company_legendary_fortitude_candidates(self, *, enemy_unit: Any) -> list[Any]:
        if not self._is_1st_company_task_force_detachment():
            return []
        enemy_root = self._sm_root(enemy_unit)
        game_map = self._sm_game_map()
        if enemy_root is None or game_map is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if not self._sm_is_first_company_veteran_unit(root):
                continue
            try:
                if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_first_company_orbital_teleportarium_candidates(self) -> list[Any]:
        if not self._is_1st_company_task_force_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if not self._sm_is_terminator_unit(root):
                continue
            if self._sm_unit_is_engaged(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_shock_cavalry_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_saga_of_the_beastslayer_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        phase_key = str(phase_name or "").strip().lower()
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if not self._sm_is_thunderwolf_cavalry(root):
                continue
            if phase_key == "movement phase" and self._sm_selected_to_move_this_phase(root):
                continue
            if phase_key == "charge phase" and self._sm_selected_to_charge_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_pinning_fire_candidates(self) -> list[Any]:
        if not self._is_saga_of_the_beastslayer_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if self._sm_selected_to_shoot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_litanies_of_purgation_candidates(self) -> list[Any]:
        if not self._is_vindication_task_force_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _queue_space_marines_first_company_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_1st_company_task_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if phase_key == "MOVEMENT_PHASE" and player is self.player and active_player is self.player:
            stratagem = self.get_by_name("DUTY AND HONOUR")
            if stratagem is not None:
                if (
                    int(getattr(self.player, "command_points", 0) or 0)
                    >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                ):
                    candidates, objective_map = self._space_marines_first_company_duty_and_honour_candidates()
                    if candidates and not self._sm_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Movement phase",
                    ):
                        payload: dict[str, Any] = {
                            "event": "phase_start",
                            "phase": "Movement phase",
                            "phase_name": "Movement phase",
                            "stratagem": stratagem.name,
                            "cp_cost": stratagem.cp_cost,
                            "candidates": candidates,
                            "objective_candidates_by_unit": objective_map,
                        }
                        if len(candidates) == 1:
                            payload["unit"] = candidates[0]
                            payload["target_unit"] = candidates[0]
                            uid = self._sm_sort_key(candidates[0])
                            objective_candidates = list(objective_map.get(uid) or [])
                            if objective_candidates:
                                payload["objective_candidates"] = objective_candidates
                                if len(objective_candidates) == 1:
                                    payload["objective"] = objective_candidates[0]
                                    payload["objective_marker"] = objective_candidates[0]
                        self._queue_reaction(payload, use_timer=False)

        if phase_key == "SHOOTING_PHASE" and player is self.player and active_player is self.player:
            stratagem = self.get_by_name("HEROES OF THE CHAPTER")
            if stratagem is not None:
                if (
                    int(getattr(self.player, "command_points", 0) or 0)
                    >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                ):
                    candidates = self._space_marines_first_company_heroes_candidates(phase_name="Shooting phase")
                    if candidates and not self._sm_reaction_already_queued(
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

        if phase_key == "FIGHT_PHASE":
            stratagem = self.get_by_name("HEROES OF THE CHAPTER")
            if stratagem is not None:
                if (
                    int(getattr(self.player, "command_points", 0) or 0)
                    >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                ):
                    candidates = self._space_marines_first_company_heroes_candidates(phase_name="Fight phase")
                    if candidates and not self._sm_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Fight phase",
                    ):
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

        if phase_key != "COMMAND_PHASE" or player is self.player:
            return
        game_map = self._sm_game_map()
        if game_map is None:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        current_player_id = str(getattr(player, "id", "") or "")
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("space_marines_terrifying_proficiency_pending")):
                continue
            due_turn = int(sr.get("space_marines_terrifying_proficiency_due_turn", 0) or 0)
            due_player_id = str(sr.get("space_marines_terrifying_proficiency_due_player_id", "") or "")
            if due_turn and due_turn != current_turn:
                continue
            if due_player_id and current_player_id and due_player_id != current_player_id:
                continue
            if not self._sm_on_battlefield(root, require_targetable=False):
                self._sm_clear_terrifying_proficiency_pending(root)
                continue
            affected: list[Any] = []
            seen_enemy: set[str] = set()
            for enemy in list(game_map.get_enemy_units(root) or []):
                enemy_root = self._sm_root(enemy)
                if enemy_root is None:
                    continue
                enemy_id = self._sm_sort_key(enemy_root)
                if enemy_id and enemy_id in seen_enemy:
                    continue
                if enemy_id:
                    seen_enemy.add(enemy_id)
                if not self._sm_is_alive(enemy_root):
                    continue
                if not bool(getattr(enemy_root, "deployed", True)):
                    continue
                if self._sm_is_in_reserves(enemy_root):
                    continue
                try:
                    distance = float(game_map.get_distance_between_units(root, enemy_root))
                except (AttributeError, TypeError, ValueError):
                    continue
                if distance > 6.0:
                    continue
                affected.append(enemy_root)
            self._sm_clear_terrifying_proficiency_pending(root)
            if not affected:
                continue
            for enemy in affected:
                enemy_sr = getattr(enemy, "special_rules", None)
                if not isinstance(enemy_sr, dict):
                    enemy_sr = {}
                if hasattr(enemy, "is_below_half_strength") and bool(enemy.is_below_half_strength()):
                    enemy_sr["battle_shock_test_modifier"] = int(enemy_sr.get("battle_shock_test_modifier", 0) or 0) - 1
                    reasons = list(enemy_sr.get("battle_shock_test_modifier_reasons", []) or [])
                    reasons.append("Terrifying Proficiency (below half-strength)")
                    enemy_sr["battle_shock_test_modifier_reasons"] = reasons
                enemy_sr["battle_shock_suppress_other_tests_phase"] = "COMMAND_PHASE"
                enemy_sr["battle_shock_suppress_other_tests_source"] = "TERRIFYING PROFICIENCY"
                enemy_sr["battle_shock_allow_suppressed_test"] = True
                enemy.special_rules = enemy_sr
                take_test = getattr(enemy, "take_battle_shock_test", None)
                if callable(take_test):
                    take_test(current_turn)

    def _queue_space_marines_first_company_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_1st_company_task_force_detachment():
            return
        if str(action or "").strip().lower() != "charge":
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        if self._sm_owned_by_player(unit, self.player):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        enemy_root = self._sm_root(unit)
        if enemy_root is None:
            return
        stratagem = self.get_by_name("LEGENDARY FORTITUDE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._space_marines_first_company_legendary_fortitude_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        if self._sm_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Charge phase",
            attacking_unit=enemy_root,
        ):
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": enemy_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_space_marines_first_company_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if not self._is_1st_company_task_force_detachment():
            return
        if destroyed_unit is None or destroyed_by_unit is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        root = self._sm_root(destroyed_by_unit)
        if root is None:
            return
        if not self._sm_owned_by_player(root, self.player):
            return
        if not self._sm_on_battlefield(root, require_targetable=True):
            return
        if not self._is_adeptus_astartes_unit(root):
            return
        if not self._sm_is_first_company_veteran_unit(root):
            return
        if not bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
            return
        stratagem = self.get_by_name("TERRIFYING PROFICIENCY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if self._sm_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "destroyed_unit": destroyed_unit,
                "destroyed_by_unit": root,
                "candidates": [root],
            },
            use_timer=False,
        )

    def _queue_space_marines_first_company_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_1st_company_task_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("ORBITAL TELEPORTARIUM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._space_marines_first_company_orbital_teleportarium_candidates()
        if not candidates:
            return
        if self._sm_reaction_already_queued(
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

    def _cleanup_space_marines_saga_of_the_beastslayer_phase_end_effects(self, *, phase: Any = None) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
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
                    key_text = str(key or "")
                    if not (
                        key_text.startswith("angelic_grace:")
                        or key_text.startswith("fuelled_by_faith:")
                        or key_text.startswith("watcher_in_the_dark:")
                    ):
                        continue
                    exp_phase = str(value.get("expires_phase", "") or "").strip().upper() if isinstance(value, dict) else ""
                    if not exp_phase or exp_phase == phase_name:
                        remove_keys.append(str(key))
                for key in remove_keys:
                    effects.pop(key, None)

        if phase_name in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            seen = set()
            for unit in list(getattr(army, "units", []) or []):
                root = self._sm_root(unit)
                if root is None:
                    continue
                uid = self._sm_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if phase_name == "FIGHT_PHASE":
                    exp = str(sr.get("space_marines_litanies_of_purgation_expires_phase", "") or "").strip().upper()
                    if sr.get("space_marines_litanies_of_purgation_active") is True and (not exp or exp == phase_name):
                        for key in (
                            "space_marines_litanies_of_purgation_active",
                            "space_marines_litanies_of_purgation_ap_bonus",
                            "space_marines_litanies_of_purgation_expires_phase",
                            "space_marines_litanies_of_purgation_turn_owner",
                            "space_marines_litanies_of_purgation_turn",
                            "space_marines_litanies_of_purgation_source",
                        ):
                            sr.pop(key, None)
                exp = str(sr.get("space_marines_heroes_of_the_chapter_expires_phase", "") or "").strip().upper()
                if sr.get("space_marines_heroes_of_the_chapter_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "space_marines_heroes_of_the_chapter_active",
                        "space_marines_heroes_of_the_chapter_hit_bonus",
                        "space_marines_heroes_of_the_chapter_wound_bonus",
                        "space_marines_heroes_of_the_chapter_wound_bonus_below_half_only",
                        "space_marines_heroes_of_the_chapter_expires_phase",
                        "space_marines_heroes_of_the_chapter_turn_owner",
                        "space_marines_heroes_of_the_chapter_turn",
                        "space_marines_heroes_of_the_chapter_source",
                    ):
                        sr.pop(key, None)
                root.special_rules = sr

        if not self._is_saga_of_the_beastslayer_detachment():
            return
        if phase_name not in ("MOVEMENT_PHASE", "CHARGE_PHASE", "SHOOTING_PHASE"):
            return

        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_name in ("MOVEMENT_PHASE", "CHARGE_PHASE"):
                exp = str(sr.get("space_marines_shock_cavalry_expires_phase", "") or "").strip().upper()
                if sr.get("space_marines_shock_cavalry_active") is True and (not exp or exp == phase_name):
                    for key, added_key in (
                        (
                            "bearer_unit_phase_move_models_only_types",
                            "space_marines_shock_cavalry_added_phase_move_models_only_types",
                        ),
                        (
                            "bearer_unit_phase_move_models_only_block_titanic_types",
                            "space_marines_shock_cavalry_added_phase_move_models_only_block_titanic_types",
                        ),
                        (
                            "move_over_low_terrain_height_types",
                            "space_marines_shock_cavalry_added_low_terrain_types",
                        ),
                        (
                            "bearer_unit_phase_move_engagement_types",
                            "space_marines_shock_cavalry_added_phase_move_engagement_types",
                        ),
                    ):
                        added = set(sr.get(added_key) or [])
                        if not added:
                            continue
                        current = list(sr.get(key) or [])
                        kept = [item for item in current if item not in added]
                        if kept:
                            sr[key] = kept
                        else:
                            sr.pop(key, None)

                    if bool(sr.get("space_marines_shock_cavalry_prev_low_terrain_height_present", False)):
                        sr["move_over_low_terrain_height_value"] = float(
                            sr.get("space_marines_shock_cavalry_prev_low_terrain_height_value", 4.0) or 4.0
                        )
                    else:
                        sr.pop("move_over_low_terrain_height_value", None)

                    for key in (
                        "space_marines_shock_cavalry_active",
                        "space_marines_shock_cavalry_expires_phase",
                        "space_marines_shock_cavalry_turn_owner",
                        "space_marines_shock_cavalry_turn",
                        "space_marines_shock_cavalry_source",
                        "space_marines_shock_cavalry_added_phase_move_models_only_types",
                        "space_marines_shock_cavalry_added_phase_move_models_only_block_titanic_types",
                        "space_marines_shock_cavalry_added_low_terrain_types",
                        "space_marines_shock_cavalry_added_phase_move_engagement_types",
                        "space_marines_shock_cavalry_prev_low_terrain_height_present",
                        "space_marines_shock_cavalry_prev_low_terrain_height_value",
                    ):
                        sr.pop(key, None)

            if phase_name == "SHOOTING_PHASE":
                exp = str(sr.get("space_marines_pinning_fire_expires_phase", "") or "").strip().upper()
                if sr.get("space_marines_pinning_fire_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "space_marines_pinning_fire_active",
                        "space_marines_pinning_fire_source",
                        "space_marines_pinning_fire_move_penalty",
                        "space_marines_pinning_fire_charge_penalty",
                        "space_marines_pinning_fire_target_keywords_any",
                        "space_marines_pinning_fire_pinned_expires_phase",
                        "space_marines_pinning_fire_expires_phase",
                        "space_marines_pinning_fire_turn_owner",
                        "space_marines_pinning_fire_turn",
                    ):
                        sr.pop(key, None)
                    self._sm_clear_ability_cache(root, "unit_post_shoot_pinned_specs")
            root.special_rules = sr

    def _queue_space_marines_mortal_wound_reactions(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
    ) -> None:
        root = self._sm_root(target_unit)
        if root is None:
            return
        if not self._sm_owned_by_player(root, self.player):
            return
        if not self._sm_on_battlefield(root, require_targetable=True):
            return
        if not self._is_adeptus_astartes_unit(root):
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

        for stratagem_name in ("ANGELIC GRACE", "FUELLED BY FAITH"):
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                continue
            if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem, target_unit=root):
                continue
            if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                continue
            if self._sm_reaction_already_queued(
                event_name="mortal_wound_allocated",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
                target_unit=root,
            ):
                continue
            self._queue_reaction(
                {
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
                },
                use_timer=False,
            )

    def _use_space_marines_mortal_wound_stratagem(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
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
            logger.error("ERROR: %s: no target unit provided", getattr(stratagem, "name", "Space Marines stratagem"))
            return False

        root = self._sm_root(unit)
        if root is None:
            return False
        if not from_pending:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                pending_root = self._sm_root(reaction.get("unit") or reaction.get("target_unit"))
                if pending_root is not root:
                    continue
                from_pending = True
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: %s: target unit is not yours", getattr(stratagem, "name", "Space Marines stratagem"))
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: %s: target must be on the battlefield and targetable", getattr(stratagem, "name", "Space Marines stratagem"))
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: %s: selected unit is not currently eligible", getattr(stratagem, "name", "Space Marines stratagem"))
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: %s: target must be an ADEPTUS ASTARTES unit", getattr(stratagem, "name", "Space Marines stratagem"))
            return False

        trigger_flag = bool(kwargs.get("mortal_wound_allocated", False))
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        if not from_pending and not trigger_flag and trigger_name not in {"mortal_wound_allocated", "mortal_wound"}:
            logger.error("ERROR: %s: missing mortal-wound trigger context", getattr(stratagem, "name", "Space Marines stratagem"))
            return False

        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "")
        phase_key = self._phase_key_from_name(phase_name) if phase_name else ""
        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])
        key_seed = self._normalize_stratagem_name(getattr(stratagem, "name", "") or "").lower().replace(" ", "_")
        for index, model in enumerate(models):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            key = f"{key_seed}:{get_entity_id(model) or index}"
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if callable(set_temporary_fnp):
                set_temporary_fnp(
                    key=key,
                    value=5,
                    source=str(getattr(stratagem, "name", "") or "Space Marines mortal-wound stratagem"),
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
                "temporary_fnp_source": str(getattr(stratagem, "name", "") or "Space Marines mortal-wound stratagem"),
                "temporary_fnp_condition": "against mortal wounds",
            }

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s gains FNP 5+ against mortal wounds this phase.",
            getattr(stratagem, "name", "Space Marines mortal-wound stratagem"),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_saga_of_the_beastslayer_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "SHOCK CAVALRY":
            return self._use_space_marines_shock_cavalry(stratagem, **kwargs)
        if name_u == "PINNING FIRE":
            return self._use_space_marines_pinning_fire(stratagem, **kwargs)
        if name_u in {"ANGELIC GRACE", "FUELLED BY FAITH"}:
            return self._use_space_marines_mortal_wound_stratagem(stratagem, **kwargs)
        return None

    def _use_space_marines_vindication_task_force_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_vindication_task_force_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "LITANIES OF PURGATION":
            return self._use_space_marines_litanies_of_purgation(stratagem, **kwargs)
        return None

    def _use_space_marines_first_company_task_force_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_1st_company_task_force_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "DUTY AND HONOUR":
            return self._use_space_marines_duty_and_honour(stratagem, **kwargs)
        if name_u == "HEROES OF THE CHAPTER":
            return self._use_space_marines_heroes_of_the_chapter(stratagem, **kwargs)
        if name_u == "LEGENDARY FORTITUDE":
            return self._use_space_marines_legendary_fortitude(stratagem, **kwargs)
        if name_u == "ORBITAL TELEPORTARIUM":
            return self._use_space_marines_orbital_teleportarium(stratagem, **kwargs)
        if name_u == "TERRIFYING PROFICIENCY":
            return self._use_space_marines_terrifying_proficiency(stratagem, **kwargs)
        return None

    def _sm_first_company_context(self, stratagem_name: str, kwargs: dict[str, Any]) -> tuple[Any, list[Any], Any, list[Any], Any, bool]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        objective_map = kwargs.get("objective_candidates_by_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        from_pending = False
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            from_pending = True
            if unit is None:
                unit = reaction.get("unit") or reaction.get("target_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if objective is None:
                objective = reaction.get("objective") or reaction.get("objective_marker")
            if not objective_candidates:
                objective_candidates = list(reaction.get("objective_candidates") or [])
            if objective_map is None:
                objective_map = reaction.get("objective_candidates_by_unit")
            if attacking_unit is None:
                attacking_unit = reaction.get("attacking_unit") or reaction.get("attacker_unit") or reaction.get("enemy_unit")
            if not kwargs.get("phase_name") and reaction.get("phase_name"):
                kwargs["phase_name"] = reaction.get("phase_name")
            break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._sm_root(unit)
        if root is not None and not objective_candidates and hasattr(objective_map, "get"):
            objective_candidates = list(objective_map.get(self._sm_sort_key(root)) or [])
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        return (unit, candidates, objective, objective_candidates, attacking_unit, from_pending)

    def _use_space_marines_duty_and_honour(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: DUTY AND HONOUR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: DUTY AND HONOUR: not your turn")
            return False

        unit, candidates, objective, objective_candidates, _attacking_unit, _from_pending = self._sm_first_company_context(
            "DUTY AND HONOUR",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: DUTY AND HONOUR: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: DUTY AND HONOUR: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: DUTY AND HONOUR: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: DUTY AND HONOUR: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_first_company_veteran_unit(root):
            logger.error("ERROR: DUTY AND HONOUR: target must be an eligible 1st Company unit")
            return False

        valid_candidates, objective_map = self._space_marines_first_company_duty_and_honour_candidates()
        if valid_candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in valid_candidates):
                logger.error("ERROR: DUTY AND HONOUR: selected unit is not currently eligible")
                return False
            if not objective_candidates:
                objective_candidates = list(objective_map.get(root_id) or [])
        if objective is None:
            logger.error("ERROR: DUTY AND HONOUR: no objective marker selected")
            return False
        if objective_candidates and objective not in objective_candidates:
            logger.error("ERROR: DUTY AND HONOUR: selected objective marker is not eligible")
            return False
        objective_location = getattr(objective, "location", None)
        if objective_location is None:
            logger.error("ERROR: DUTY AND HONOUR: objective marker location unavailable")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False
        if hasattr(objective_location, "set_sticky_control"):
            objective_location.set_sticky_control(self.player, source="space_marines_duty_and_honour")
        else:
            objective_location.sticky_controller = self.player
            objective_location.sticky_source = "space_marines_duty_and_honour"
            objective_location.controlling_player = self.player
        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: DUTY AND HONOUR: selected objective remains under your control until broken.")
        return True

    def _use_space_marines_heroes_of_the_chapter(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: HEROES OF THE CHAPTER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: HEROES OF THE CHAPTER: not your Shooting phase")
            return False

        unit, candidates, _objective, _objective_candidates, _attacking_unit, _from_pending = self._sm_first_company_context(
            "HEROES OF THE CHAPTER",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: HEROES OF THE CHAPTER: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: HEROES OF THE CHAPTER: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: HEROES OF THE CHAPTER: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: HEROES OF THE CHAPTER: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_first_company_veteran_unit(root):
            logger.error("ERROR: HEROES OF THE CHAPTER: target must be an eligible 1st Company unit")
            return False
        if phase_name == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: HEROES OF THE CHAPTER: target has already been selected to shoot this phase")
            return False
        if phase_name == "fight phase" and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: HEROES OF THE CHAPTER: target has already been selected to fight this phase")
            return False

        valid_candidates = self._space_marines_first_company_heroes_candidates(
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        )
        if valid_candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in valid_candidates):
                logger.error("ERROR: HEROES OF THE CHAPTER: selected unit is not currently eligible")
                return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: HEROES OF THE CHAPTER: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_heroes_of_the_chapter_active"] = True
        sr["space_marines_heroes_of_the_chapter_hit_bonus"] = 1
        sr["space_marines_heroes_of_the_chapter_wound_bonus"] = 1
        sr["space_marines_heroes_of_the_chapter_wound_bonus_below_half_only"] = True
        sr["space_marines_heroes_of_the_chapter_expires_phase"] = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["space_marines_heroes_of_the_chapter_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_heroes_of_the_chapter_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_heroes_of_the_chapter_source"] = str(getattr(stratagem, "name", "") or "HEROES OF THE CHAPTER")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: HEROES OF THE CHAPTER: %s gains +1 to hit this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_space_marines_legendary_fortitude(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: LEGENDARY FORTITUDE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: LEGENDARY FORTITUDE: not opponent's Charge phase")
            return False

        unit, candidates, _objective, _objective_candidates, attacking_unit, _from_pending = self._sm_first_company_context(
            "LEGENDARY FORTITUDE",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: LEGENDARY FORTITUDE: no target unit provided")
            return False
        root = self._sm_root(unit)
        enemy_root = self._sm_root(attacking_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: LEGENDARY FORTITUDE: missing charging unit context")
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: LEGENDARY FORTITUDE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: LEGENDARY FORTITUDE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: LEGENDARY FORTITUDE: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_first_company_veteran_unit(root):
            logger.error("ERROR: LEGENDARY FORTITUDE: target must be an eligible 1st Company unit")
            return False

        valid_candidates = self._space_marines_first_company_legendary_fortitude_candidates(enemy_unit=enemy_root)
        if valid_candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in valid_candidates):
                logger.error("ERROR: LEGENDARY FORTITUDE: selected unit is not currently eligible")
                return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Charge phase"):
            logger.error("ERROR: LEGENDARY FORTITUDE: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "melee",
            "expires_phase": "FIGHT_PHASE",
            "source": str(getattr(stratagem, "name", "") or "LEGENDARY FORTITUDE"),
        }
        if hasattr(self, "_append_defensive_effect"):
            self._append_defensive_effect(root, "defensive_damage_reductions", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_damage_reductions", []) or [])
            items.append(entry)
            sr["defensive_damage_reductions"] = items
            root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: LEGENDARY FORTITUDE: %s reduces incoming melee Damage by 1 until end of turn.", getattr(root, "name", "Unit"))
        return True

    def _use_space_marines_orbital_teleportarium(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ORBITAL TELEPORTARIUM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ORBITAL TELEPORTARIUM: not opponent's Fight phase")
            return False

        unit, candidates, _objective, _objective_candidates, _attacking_unit, _from_pending = self._sm_first_company_context(
            "ORBITAL TELEPORTARIUM",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: ORBITAL TELEPORTARIUM: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_terminator_unit(root):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: target must be a TERMINATOR unit")
            return False
        if self._sm_unit_is_engaged(root):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: target cannot be within Engagement Range")
            return False

        valid_candidates = self._space_marines_first_company_orbital_teleportarium_candidates()
        if valid_candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in valid_candidates):
                logger.error("ERROR: ORBITAL TELEPORTARIUM: selected unit is not currently eligible")
                return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False
        if not bool(root.enter_strategic_reserves_midgame(game=self.game, game_map=self._sm_game_map(), reason=stratagem.name)):
            logger.error("ERROR: ORBITAL TELEPORTARIUM: failed to place target into Strategic Reserves")
            return False

        arrival_turn = self._sm_next_owner_movement_phase_turn(self.player)
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["midgame_temp_deep_strike"] = True
            sr["midgame_temp_deep_strike_turn_owner"] = str(getattr(self.player, "id", "") or "")
            sr["midgame_temp_deep_strike_must_arrive_turn"] = int(arrival_turn)
            sr["midgame_temp_deep_strike_source"] = str(getattr(stratagem, "name", "") or "ORBITAL TELEPORTARIUM")
            member.special_rules = sr
            self._sm_clear_ability_cache(member, "deep_strike")

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ORBITAL TELEPORTARIUM: %s enters Strategic Reserves and returns next Movement phase via Deep Strike.", getattr(root, "name", "Unit"))
        return True

    def _use_space_marines_terrifying_proficiency(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: TERRIFYING PROFICIENCY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TERRIFYING PROFICIENCY: not your Fight phase")
            return False

        unit, candidates, _objective, _objective_candidates, _attacking_unit, from_pending = self._sm_first_company_context(
            "TERRIFYING PROFICIENCY",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: TERRIFYING PROFICIENCY: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: TERRIFYING PROFICIENCY: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: TERRIFYING PROFICIENCY: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: TERRIFYING PROFICIENCY: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_first_company_veteran_unit(root):
            logger.error("ERROR: TERRIFYING PROFICIENCY: target must be an eligible 1st Company unit")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
            logger.error("ERROR: TERRIFYING PROFICIENCY: target must have made a Charge move this turn")
            return False
        if candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in candidates):
                logger.error("ERROR: TERRIFYING PROFICIENCY: selected unit is not currently eligible")
                return False
        if not from_pending and not bool(kwargs.get("destroyed_enemy_triggered", False)):
            logger.error("ERROR: TERRIFYING PROFICIENCY: missing destroyed-enemy trigger context")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: TERRIFYING PROFICIENCY: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        due_turn, due_player_id = self._sm_next_enemy_command_phase_turn()
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_terrifying_proficiency_pending"] = True
        sr["space_marines_terrifying_proficiency_due_turn"] = int(due_turn)
        sr["space_marines_terrifying_proficiency_due_player_id"] = str(due_player_id or "")
        sr["space_marines_terrifying_proficiency_source"] = str(getattr(stratagem, "name", "") or "TERRIFYING PROFICIENCY")
        sr["space_marines_terrifying_proficiency_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_terrifying_proficiency_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: TERRIFYING PROFICIENCY: %s will force nearby enemies to test for Battle-shock in the opponent's next Command phase.", getattr(root, "name", "Unit"))
        return True

    def _use_space_marines_litanies_of_purgation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_vindication_task_force_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: LITANIES OF PURGATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: LITANIES OF PURGATION: not your Fight phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LITANIES OF PURGATION: no target unit provided")
            return False

        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: LITANIES OF PURGATION: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: LITANIES OF PURGATION: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: LITANIES OF PURGATION: target must be an ADEPTUS ASTARTES unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: LITANIES OF PURGATION: target has already been selected to fight this phase")
            return False

        eligible = candidates or self._space_marines_litanies_of_purgation_candidates()
        if eligible:
            eid = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != eid for candidate in eligible):
                logger.error("ERROR: LITANIES OF PURGATION: selected unit is not currently eligible")
                return False

        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: LITANIES OF PURGATION: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_litanies_of_purgation_active"] = True
        sr["space_marines_litanies_of_purgation_ap_bonus"] = 1
        sr["space_marines_litanies_of_purgation_expires_phase"] = "FIGHT_PHASE"
        sr["space_marines_litanies_of_purgation_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_litanies_of_purgation_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_litanies_of_purgation_source"] = str(getattr(stratagem, "name", "") or "LITANIES OF PURGATION")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LITANIES OF PURGATION: %s improves AP by 1 while it or its target is within objective range this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_shock_cavalry(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_saga_of_the_beastslayer_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            logger.error("ERROR: SHOCK CAVALRY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SHOCK CAVALRY: not your turn")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHOCK CAVALRY: no target unit provided")
            return False

        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: SHOCK CAVALRY: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SHOCK CAVALRY: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: SHOCK CAVALRY: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_thunderwolf_cavalry(root):
            logger.error("ERROR: SHOCK CAVALRY: target must be a THUNDERWOLF CAVALRY unit")
            return False

        if phase_name == "movement phase" and self._sm_selected_to_move_this_phase(root):
            logger.error("ERROR: SHOCK CAVALRY: target has already been selected to move this phase")
            return False
        if phase_name == "charge phase" and self._sm_selected_to_charge_this_phase(root):
            logger.error("ERROR: SHOCK CAVALRY: target has already declared a charge this phase")
            return False

        eligible = candidates or self._space_marines_shock_cavalry_candidates(phase_name=phase_name)
        if eligible:
            eid = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != eid for candidate in eligible):
                logger.error("ERROR: SHOCK CAVALRY: selected unit is not currently eligible")
                return False

        phase_label = "Movement phase" if phase_name == "movement phase" else "Charge phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: SHOCK CAVALRY: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        move_types = {"move", "advance", "fall_back"} if phase_name == "movement phase" else {"charge"}
        engagement_move_types = {"move", "advance", "fall_back"} if phase_name == "movement phase" else set()

        def _merge_move_types(rule_key: str, added_key: str, values: set[str]) -> None:
            current = set(sr.get(rule_key) or [])
            added = sorted([move_type for move_type in values if move_type not in current])
            merged = sorted(current.union(values))
            if merged:
                sr[rule_key] = merged
            if added:
                sr[added_key] = added
            else:
                sr.pop(added_key, None)

        _merge_move_types(
            "bearer_unit_phase_move_models_only_types",
            "space_marines_shock_cavalry_added_phase_move_models_only_types",
            set(move_types),
        )
        _merge_move_types(
            "bearer_unit_phase_move_models_only_block_titanic_types",
            "space_marines_shock_cavalry_added_phase_move_models_only_block_titanic_types",
            set(move_types),
        )
        _merge_move_types(
            "move_over_low_terrain_height_types",
            "space_marines_shock_cavalry_added_low_terrain_types",
            set(move_types),
        )
        _merge_move_types(
            "bearer_unit_phase_move_engagement_types",
            "space_marines_shock_cavalry_added_phase_move_engagement_types",
            set(engagement_move_types),
        )

        low_height_present = "move_over_low_terrain_height_value" in sr
        sr["space_marines_shock_cavalry_prev_low_terrain_height_present"] = bool(low_height_present)
        if low_height_present:
            sr["space_marines_shock_cavalry_prev_low_terrain_height_value"] = float(
                sr.get("move_over_low_terrain_height_value", 4.0) or 4.0
            )
        current_height = float(sr.get("move_over_low_terrain_height_value", 0.0) or 0.0)
        sr["move_over_low_terrain_height_value"] = max(4.0, current_height)

        sr["space_marines_shock_cavalry_active"] = True
        sr["space_marines_shock_cavalry_expires_phase"] = (
            "MOVEMENT_PHASE" if phase_name == "movement phase" else "CHARGE_PHASE"
        )
        sr["space_marines_shock_cavalry_source"] = str(getattr(stratagem, "name", "") or "SHOCK CAVALRY")
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["space_marines_shock_cavalry_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["space_marines_shock_cavalry_turn"] = turn

        root.special_rules = sr
        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHOCK CAVALRY: %s gains move-through models/low-terrain movement for this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_pinning_fire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_saga_of_the_beastslayer_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PINNING FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PINNING FIRE: not your turn")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PINNING FIRE: no target unit provided")
            return False

        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: PINNING FIRE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: PINNING FIRE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: PINNING FIRE: target must be an ADEPTUS ASTARTES unit")
            return False
        if self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: PINNING FIRE: target has already been selected to shoot this phase")
            return False

        eligible = candidates or self._space_marines_pinning_fire_candidates()
        if eligible:
            eid = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != eid for candidate in eligible):
                logger.error("ERROR: PINNING FIRE: selected unit is not currently eligible")
                return False

        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: PINNING FIRE: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_pinning_fire_active"] = True
        sr["space_marines_pinning_fire_source"] = str(getattr(stratagem, "name", "") or "PINNING FIRE")
        sr["space_marines_pinning_fire_move_penalty"] = -2
        sr["space_marines_pinning_fire_charge_penalty"] = -2
        sr["space_marines_pinning_fire_target_keywords_any"] = ["CHARACTER", "MONSTER", "VEHICLE"]
        sr["space_marines_pinning_fire_pinned_expires_phase"] = "SHOOTING_PHASE"
        sr["space_marines_pinning_fire_expires_phase"] = "SHOOTING_PHASE"
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["space_marines_pinning_fire_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["space_marines_pinning_fire_turn"] = turn
        root.special_rules = sr
        self._sm_clear_ability_cache(root, "unit_post_shoot_pinned_specs")

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PINNING FIRE: %s can pin a hit enemy CHARACTER/MONSTER/VEHICLE after it shoots this phase.",
            getattr(root, "name", "Unit"),
        )
        return True
