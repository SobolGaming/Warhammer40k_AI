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

    def _is_anvil_siege_force_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_anvil_siege_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_bastion_task_force_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_bastion_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_black_spear_task_force_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_black_spear_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_vindication_task_force_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_vindication_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_angelic_inheritors_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_angelic_inheritors", None) if mgr is not None else None
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
    def _sm_selected_to_fight_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "fought_this_phase", False))

    def _sm_resolve_units(self, selected: Any) -> list[Any]:
        if selected is None:
            return []
        if isinstance(selected, (list, tuple, set)):
            values = list(selected)
        else:
            values = [selected]
        out: list[Any] = []
        seen: set[str] = set()
        for value in list(values or []):
            root = self._sm_root(value)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return out

    def _sm_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        root_id = self._sm_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._sm_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            candidate_id = self._sm_sort_key(candidate_root)
            if root_id and candidate_id and root_id == candidate_id:
                return True
        return False

    @staticmethod
    def _sm_unit_models(unit: Any) -> list[Any]:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            return list(get_models() or [])
        return list(getattr(unit, "models", []) or [])

    def _sm_alive_model_count(self, unit: Any) -> int:
        count = 0
        for model in self._sm_unit_models(unit):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if is_alive:
                count += 1
        return int(count)

    def _sm_resolve_selected_model(self, selection: Any, models: list[Any]) -> Any:
        if selection is None:
            return None
        for model in list(models or []):
            if model is selection:
                return model
        selection_id = str(get_entity_id(selection) or selection or "")
        if not selection_id:
            return None
        for model in list(models or []):
            if str(get_entity_id(model) or "") == selection_id:
                return model
        return None

    def _sm_is_character_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "_attached_unit_has_keyword", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root, "CHARACTER"))
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any("CHARACTER"))
        return False

    def _sm_is_infantry_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "_attached_unit_has_keyword", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root, "INFANTRY"))
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any("INFANTRY"))
        return False

    def _sm_is_battleline_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "_attached_unit_has_keyword", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root, "BATTLELINE"))
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any("BATTLELINE"))
        return False

    def _sm_is_kill_team_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        attached_checker = getattr(root, "attached_unit_has_kill_team", None)
        if callable(attached_checker) and bool(attached_checker()):
            return True
        local_checker = getattr(root, "has_kill_team", None)
        if callable(local_checker) and bool(local_checker()):
            return True
        mgr = self._sm_detachment_mgr()
        named_checker = getattr(mgr, "_attached_unit_has_named_ability", None) if mgr is not None else None
        if callable(named_checker) and bool(named_checker(root, "Kill Team")):
            return True
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("KILL TEAM")):
            return True
        has_keyword = getattr(root, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("KILL TEAM")):
            return True
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "kill team" in name

    def _sm_is_jump_pack_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "_attached_unit_has_keyword", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root, "JUMP PACK"))
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any("JUMP PACK"))
        return False

    @staticmethod
    def _sm_model_is_character(model: Any) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("CHARACTER")):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("CHARACTER")):
            return True
        parent = getattr(model, "parent_unit", None)
        has_keyword_local = getattr(parent, "has_keyword_local", None) if parent is not None else None
        return bool(has_keyword_local("CHARACTER")) if callable(has_keyword_local) else False

    @staticmethod
    def _sm_is_the_sanguinor(unit: Any) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("THE SANGUINOR")):
            return True
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("THE SANGUINOR")):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "the sanguinor" in name

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

    def _sm_unit_within_any_objective_range(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        game_map = self._sm_game_map()
        if root is None or game_map is None:
            return False
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return False
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            try:
                if bool(is_within(location)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _space_marines_anvil_hail_loss_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        snapshots = getattr(self, "_space_marines_anvil_hail_loss_snapshots_cache", None)
        if isinstance(snapshots, dict):
            return snapshots
        snapshots = {}
        setattr(self, "_space_marines_anvil_hail_loss_snapshots_cache", snapshots)
        return snapshots

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

    def _sm_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._sm_root(unit)
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

    def _cleanup_space_marines_angelic_instant_of_grace_command_phase_effects(self, *, player: Any, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE" or player is not self.player:
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
            if not isinstance(sr, dict) or not bool(sr.get("space_marines_instant_of_grace_active")):
                continue
            due_turn = int(sr.get("space_marines_instant_of_grace_due_turn", 0) or 0)
            due_player_id = str(sr.get("space_marines_instant_of_grace_due_player_id", "") or "")
            if due_turn and current_turn and current_turn < due_turn:
                continue
            if due_player_id and current_player_id and due_player_id != current_player_id:
                continue
            model_id = str(sr.get("space_marines_instant_of_grace_model_id", "") or "")
            if model_id and bool(sr.get("space_marines_instant_of_grace_added_model_character")):
                for model in self._sm_unit_models(root):
                    if str(get_entity_id(model) or "") != model_id:
                        continue
                    current_keywords = list(getattr(model, "keywords", []) or [])
                    updated_keywords: list[Any] = []
                    removed = False
                    for keyword in current_keywords:
                        if not removed and str(keyword or "").strip().upper() == "CHARACTER":
                            removed = True
                            continue
                        updated_keywords.append(keyword)
                    model.keywords = updated_keywords
                    break
            if bool(sr.get("space_marines_instant_of_grace_added_unit_character")):
                current_keywords = list(sr.get("ability_added_keywords", []) or [])
                updated_keywords = []
                removed = False
                for keyword in current_keywords:
                    if not removed and str(keyword or "").strip().upper() == "CHARACTER":
                        removed = True
                        continue
                    updated_keywords.append(keyword)
                if updated_keywords:
                    sr["ability_added_keywords"] = updated_keywords
                else:
                    sr.pop("ability_added_keywords", None)
            for key in (
                "space_marines_instant_of_grace_active",
                "space_marines_instant_of_grace_model_id",
                "space_marines_instant_of_grace_due_turn",
                "space_marines_instant_of_grace_due_player_id",
                "space_marines_instant_of_grace_added_model_character",
                "space_marines_instant_of_grace_added_unit_character",
                "space_marines_instant_of_grace_source",
                "space_marines_instant_of_grace_turn_owner",
                "space_marines_instant_of_grace_turn",
            ):
                sr.pop(key, None)
            root.special_rules = sr
            invalidate = getattr(root, "_invalidate_ability_cache", None)
            if callable(invalidate):
                invalidate()

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

    def _space_marines_anvil_shooting_candidates(self) -> list[Any]:
        if not self._is_anvil_siege_force_detachment():
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

    def _space_marines_anvil_not_one_backwards_step_candidates(self) -> list[Any]:
        if not self._is_anvil_siege_force_detachment():
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
            if not self._sm_is_infantry_unit(root):
                continue
            if not self._sm_unit_within_any_objective_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_anvil_rigid_discipline_candidates(self) -> list[Any]:
        if not self._is_anvil_siege_force_detachment():
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
            if not self._sm_unit_is_engaged(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_bastion_phase_start_candidates(self, *, phase_key: str) -> list[Any]:
        if not self._is_bastion_task_force_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        normalized_phase = str(phase_key or "").strip().lower()
        if normalized_phase not in {"shooting phase", "fight phase"}:
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
            if normalized_phase == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
                continue
            if normalized_phase == "fight phase" and self._sm_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_bastion_heresy_undone_candidates(self, *, phase_key: str) -> list[Any]:
        if not self._is_bastion_task_force_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        normalized_phase = str(phase_key or "").strip().lower()
        if normalized_phase not in {"shooting phase", "charge phase"}:
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
            if self._sm_is_battleline_unit(root):
                continue
            if normalized_phase == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
                continue
            if normalized_phase == "charge phase" and self._sm_selected_to_charge_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_bastion_post_attack_source(self, *, attacker_unit: Any, hits_by_target: Any) -> Any:
        if not self._is_bastion_task_force_detachment():
            return None
        if attacker_unit is None or not isinstance(hits_by_target, dict):
            return None
        root = self._sm_root(attacker_unit)
        if root is None:
            return None
        if not self._sm_owned_by_player(root, self.player):
            return None
        if not self._sm_on_battlefield(root, require_targetable=True):
            return None
        if not self._is_adeptus_astartes_unit(root):
            return None
        if not self._sm_is_battleline_unit(root):
            return None
        for target_unit, hits in list((hits_by_target or {}).items()):
            if target_unit is None or int(hits or 0) <= 0:
                continue
            target_root = self._sm_root(target_unit)
            if target_root is None:
                continue
            if self._sm_owned_by_player(target_root, self.player):
                continue
            if not self._sm_is_alive(target_root):
                continue
            return root
        return None

    def _sm_bastion_pending_effect_matches(
        self,
        root: Any,
        *,
        prefix: str,
        owner_id: str,
        turn: int,
        phase_key: str,
    ) -> bool:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get(f"{prefix}_pending", False)):
            return False
        effect_owner = str(sr.get(f"{prefix}_pending_turn_owner", "") or "")
        effect_phase = str(sr.get(f"{prefix}_pending_phase", "") or "").strip().upper()
        try:
            effect_turn = int(sr.get(f"{prefix}_pending_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        if owner_id and effect_owner and owner_id != effect_owner:
            return False
        if phase_key and effect_phase and phase_key != effect_phase:
            return False
        if turn and effect_turn and turn != effect_turn:
            return False
        return True

    def _sm_bastion_set_pending_effect(
        self,
        root: Any,
        *,
        prefix: str,
        owner_id: str,
        turn: int,
        phase_key: str,
        source_name: str,
    ) -> None:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr[f"{prefix}_pending"] = True
        sr[f"{prefix}_pending_turn_owner"] = str(owner_id or "")
        sr[f"{prefix}_pending_turn"] = int(turn or 0)
        sr[f"{prefix}_pending_phase"] = str(phase_key or "").strip().upper()
        sr[f"{prefix}_source"] = str(source_name or "").strip() or prefix
        root.special_rules = sr

    def _sm_bastion_clear_pending_effect(self, root: Any, *, prefix: str) -> None:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            f"{prefix}_pending",
            f"{prefix}_pending_turn_owner",
            f"{prefix}_pending_turn",
            f"{prefix}_pending_phase",
            f"{prefix}_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def _sm_bastion_last_scan_target(self, root: Any, *, owner_id: str, turn: int, phase_key: str) -> Any:
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        target_id = str(sr.get("interlocking_tactics_last_scan_target_id", "") or "")
        if not target_id:
            return None
        effect_owner = str(sr.get("interlocking_tactics_last_scan_owner", "") or "")
        effect_phase = str(sr.get("interlocking_tactics_last_scan_phase", "") or "").strip().upper()
        try:
            effect_turn = int(sr.get("interlocking_tactics_last_scan_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        if owner_id and effect_owner and owner_id != effect_owner:
            return None
        if phase_key and effect_phase and phase_key != effect_phase:
            return None
        if turn and effect_turn and turn != effect_turn:
            return None
        registry = getattr(self.game, "entity_registry", None) if self.game is not None else None
        if registry is None or not callable(getattr(registry, "get", None)):
            return None
        return registry.get(target_id, kind="unit")

    def _apply_space_marines_bastion_guided_disruption_effect(
        self,
        *,
        target_unit: Any,
        owner_id: str,
        turn: int,
        source_name: str,
    ) -> bool:
        target_root = self._sm_root(target_unit)
        if target_root is None or not self._sm_is_alive(target_root):
            return False
        has_keyword = getattr(target_root, "has_any_keyword", None)
        if not callable(has_keyword):
            has_keyword = getattr(target_root, "has_keyword", None)
        if callable(has_keyword):
            if bool(has_keyword("MONSTER")) or bool(has_keyword("VEHICLE")):
                return False
        apply_fn = getattr(target_root, "apply_pinned", None)
        if callable(apply_fn):
            apply_fn(
                owner_id=str(owner_id or ""),
                turn=int(turn or 0),
                source=str(source_name or "GUIDED DISRUPTION"),
                move_penalty=-2,
                charge_penalty=-2,
                expires_phase="COMMAND_PHASE",
            )
        else:
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["pinned_active"] = True
            sr["pinned_owner"] = str(owner_id or "")
            sr["pinned_turn"] = int(turn or 0)
            sr["pinned_source"] = str(source_name or "GUIDED DISRUPTION")
            sr["pinned_move_penalty"] = -2
            sr["pinned_charge_penalty"] = -2
            sr["pinned_expires_phase"] = "COMMAND_PHASE"
            target_root.special_rules = sr
        logger.info(
            "INFO: GUIDED DISRUPTION: %s is pinned until the start of your next turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _apply_space_marines_bastion_shock_bombardment_effect(
        self,
        *,
        target_unit: Any,
        owner_id: str,
        turn: int,
        source_name: str,
    ) -> bool:
        target_root = self._sm_root(target_unit)
        if target_root is None or not self._sm_is_alive(target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["post_shoot_suppressed_active"] = True
        sr["post_shoot_suppressed_owner"] = str(owner_id or "")
        sr["post_shoot_suppressed_turn"] = int(turn or 0)
        sr["post_shoot_suppressed_source"] = str(source_name or "SHOCK BOMBARDMENT")
        sr["post_shoot_suppressed_attack_types"] = ["melee", "ranged"]
        target_root.special_rules = sr
        logger.info(
            "INFO: SHOCK BOMBARDMENT: %s is suppressed until the start of your next turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _sm_bastion_resolve_last_scan_effect(
        self,
        *,
        root: Any,
        prefix: str,
        owner_id: str,
        turn: int,
        phase_key: str,
        source_name: str,
    ) -> bool:
        target_unit = self._sm_bastion_last_scan_target(
            root,
            owner_id=owner_id,
            turn=turn,
            phase_key=phase_key,
        )
        if target_unit is None:
            return False
        if prefix == "space_marines_bastion_guided_disruption":
            self._apply_space_marines_bastion_guided_disruption_effect(
                target_unit=target_unit,
                owner_id=owner_id,
                turn=turn,
                source_name=source_name,
            )
            return True
        if prefix == "space_marines_bastion_shock_bombardment":
            self._apply_space_marines_bastion_shock_bombardment_effect(
                target_unit=target_unit,
                owner_id=owner_id,
                turn=turn,
                source_name=source_name,
            )
            return True
        return False

    def _queue_space_marines_bastion_post_attack_reactions(
        self,
        *,
        event_name: str,
        phase_name: str,
        source_unit: Any,
    ) -> None:
        if source_unit is None:
            return
        for stratagem_name in ("GUIDED DISRUPTION", "SHOCK BOMBARDMENT"):
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                continue
            if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
                continue
            if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                continue
            if self._sm_reaction_already_queued(
                event_name=event_name,
                stratagem_name=stratagem.name,
                phase_name=phase_name,
                target_unit=source_unit,
            ):
                continue
            payload = {
                "event": event_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": [source_unit],
                "unit": source_unit,
                "target_unit": source_unit,
            }
            self._queue_reaction(payload, use_timer=False)

    def _space_marines_angelic_focused_fury_candidates(self) -> list[Any]:
        if not self._is_angelic_inheritors_detachment():
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
            if self._sm_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_angelic_strike_now_for_glory_candidates(self) -> list[Any]:
        if not self._is_angelic_inheritors_detachment():
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

    def _space_marines_angelic_instant_of_grace_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_angelic_inheritors_detachment():
            return ([], {})
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return ([], {})
        out: list[Any] = []
        model_map: dict[str, list[Any]] = {}
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
            if not self._sm_is_infantry_unit(root):
                continue
            eligible_models: list[Any] = []
            for model in self._sm_unit_models(root):
                is_alive_attr = getattr(model, "is_alive", True)
                is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
                if not is_alive:
                    continue
                if self._sm_model_is_character(model):
                    continue
                eligible_models.append(model)
            if not eligible_models:
                continue
            out.append(root)
            if uid:
                model_map[uid] = eligible_models
        return (sorted(out, key=self._sm_sort_key), model_map)

    def _space_marines_angelic_in_the_shadow_candidates(self, target_units: list[Any]) -> list[Any]:
        if not self._is_angelic_inheritors_detachment():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
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
            if not self._sm_is_character_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_angelic_unto_burning_skies_candidates(self) -> list[Any]:
        if not self._is_angelic_inheritors_detachment():
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
            if not self._sm_is_jump_pack_unit(root):
                continue
            if self._sm_unit_is_engaged(root) and not self._sm_is_the_sanguinor(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _queue_space_marines_angelic_inheritors_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_angelic_inheritors_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if phase_key == "COMMAND_PHASE" and player is self.player:
            self._cleanup_space_marines_angelic_instant_of_grace_command_phase_effects(player=player, phase=phase)
            if active_player is self.player:
                stratagem = self.get_by_name("INSTANT OF GRACE")
                if stratagem is not None:
                    if (
                        int(getattr(self.player, "command_points", 0) or 0)
                        >= self._sm_effective_cp_cost(self.player, stratagem)
                        and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                    ):
                        candidates, model_map = self._space_marines_angelic_instant_of_grace_candidates()
                        if candidates and not self._sm_reaction_already_queued(
                            event_name="phase_start",
                            stratagem_name=stratagem.name,
                            phase_name="Command phase",
                        ):
                            payload: dict[str, Any] = {
                                "event": "phase_start",
                                "phase": "Command phase",
                                "phase_name": "Command phase",
                                "stratagem": stratagem.name,
                                "cp_cost": stratagem.cp_cost,
                                "candidates": candidates,
                                "model_candidates_by_unit": model_map,
                            }
                            if len(candidates) == 1:
                                payload["unit"] = candidates[0]
                                payload["target_unit"] = candidates[0]
                                model_candidates = list(model_map.get(self._sm_sort_key(candidates[0])) or [])
                                if model_candidates:
                                    payload["model_candidates"] = model_candidates
                                    if len(model_candidates) == 1:
                                        payload["model"] = model_candidates[0]
                                        payload["target_model"] = model_candidates[0]
                            self._queue_reaction(payload, use_timer=False)

        if phase_key == "SHOOTING_PHASE" and player is self.player and active_player is self.player:
            stratagem = self.get_by_name("STRIKE NOW FOR GLORY")
            if stratagem is not None:
                if (
                    int(getattr(self.player, "command_points", 0) or 0)
                    >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                ):
                    candidates = self._space_marines_angelic_strike_now_for_glory_candidates()
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
            stratagem = self.get_by_name("FOCUSED FURY")
            if stratagem is None:
                return
            if (
                int(getattr(self.player, "command_points", 0) or 0)
                < self._sm_effective_cp_cost(self.player, stratagem)
            ):
                return
            if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                return
            candidates = self._space_marines_angelic_focused_fury_candidates()
            if not candidates:
                return
            if self._sm_reaction_already_queued(
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

    def _queue_space_marines_angelic_shooting_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_angelic_inheritors_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacking_root = self._sm_root(attacking_unit)
        if attacking_root is None or not self._sm_is_alive(attacking_root):
            return
        if self._sm_owned_by_player(attacking_root, self.player):
            return
        stratagem = self.get_by_name("IN THE SHADOW OF GREAT WINGS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._space_marines_angelic_in_the_shadow_candidates(list(target_units or []))
        if not candidates:
            return
        if self._sm_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            attacking_unit=attacking_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_space_marines_angelic_inheritors_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_angelic_inheritors_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE" or player is self.player:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        stratagem = self.get_by_name("UNTO THE BURNING SKIES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._space_marines_angelic_unto_burning_skies_candidates()
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

    def _queue_space_marines_anvil_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_anvil_siege_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        self._space_marines_anvil_hail_loss_snapshots().clear()

        if phase_key == "COMMAND_PHASE" and player is self.player and active_player is self.player:
            stratagem = self.get_by_name("NOT ONE BACKWARDS STEP")
            if stratagem is not None:
                if (
                    int(getattr(self.player, "command_points", 0) or 0)
                    >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                ):
                    candidates = self._space_marines_anvil_not_one_backwards_step_candidates()
                    if candidates and not self._sm_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Command phase",
                    ):
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

        if phase_key == "SHOOTING_PHASE" and player is self.player and active_player is self.player:
            candidates = self._space_marines_anvil_shooting_candidates()
            if not candidates:
                return
            for stratagem_name in ("BATTLE DRILL RECALL", "NO THREAT TOO GREAT"):
                stratagem = self.get_by_name(stratagem_name)
                if stratagem is None:
                    continue
                if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
                    continue
                if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                if self._sm_reaction_already_queued(
                    event_name="phase_start",
                    stratagem_name=stratagem.name,
                    phase_name="Shooting phase",
                ):
                    continue
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

    def _capture_space_marines_anvil_shooting_targets_selected(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_anvil_siege_force_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        attacker_root = self._sm_root(attacking_unit)
        if attacker_root is None or not self._sm_is_alive(attacker_root):
            return
        if self._sm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("HAIL OF VENGEANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_id = self._sm_sort_key(attacker_root)
        if not attacker_id:
            return

        snapshot_by_unit: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if not uid or uid in seen:
                continue
            seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=False):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            models_before = self._sm_alive_model_count(root)
            if models_before <= 0:
                continue
            snapshot_by_unit[uid] = {
                "unit": root,
                "models_before": models_before,
            }
        if not snapshot_by_unit:
            return
        self._space_marines_anvil_hail_loss_snapshots()[attacker_id] = snapshot_by_unit

    def _queue_space_marines_anvil_shooting_resolved_reactions(self, *, attacker_unit: Any) -> None:
        if not self._is_anvil_siege_force_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        attacker_root = self._sm_root(attacker_unit)
        if attacker_root is None or not self._sm_is_alive(attacker_root):
            return
        if self._sm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("HAIL OF VENGEANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_id = self._sm_sort_key(attacker_root)
        if not attacker_id:
            return

        snapshots = self._space_marines_anvil_hail_loss_snapshots()
        snapshot_by_unit = dict(snapshots.pop(attacker_id, {}) or {})
        if not snapshot_by_unit:
            return

        can_shoot_fn = getattr(getattr(self, "game", None), "_setup_reactive_can_shoot_target", None)
        if not callable(can_shoot_fn):
            return

        candidates: list[Any] = []
        for unit_id in sorted(snapshot_by_unit):
            entry = snapshot_by_unit.get(unit_id)
            if not isinstance(entry, dict):
                continue
            root = self._sm_root(entry.get("unit"))
            if root is None:
                continue
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            before = int(entry.get("models_before", 0) or 0)
            if before <= 0:
                continue
            if self._sm_alive_model_count(root) >= before:
                continue
            if not can_shoot_fn(root, attacker_root):
                continue
            candidates.append(root)
        candidates.sort(key=self._sm_sort_key)
        if not candidates:
            return
        if self._sm_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            attacking_unit=attacker_root,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_space_marines_anvil_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_anvil_siege_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        stratagem = self.get_by_name("RIGID DISCIPLINE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._space_marines_anvil_rigid_discipline_candidates()
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

    def _cleanup_space_marines_anvil_siege_force_phase_end_effects(self, *, player: Any, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
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
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_key == "SHOOTING_PHASE":
                for key in (
                    "space_marines_battle_drill_recall_active",
                    "space_marines_battle_drill_recall_crit_hit_threshold",
                    "space_marines_battle_drill_recall_expires_phase",
                    "space_marines_battle_drill_recall_turn_owner",
                    "space_marines_battle_drill_recall_turn",
                    "space_marines_battle_drill_recall_source",
                    "space_marines_no_threat_too_great_active",
                    "space_marines_no_threat_too_great_expires_phase",
                    "space_marines_no_threat_too_great_turn_owner",
                    "space_marines_no_threat_too_great_turn",
                    "space_marines_no_threat_too_great_source",
                ):
                    sr.pop(key, None)
            if phase_key == "FIGHT_PHASE" and player is self.player:
                for key in (
                    "space_marines_not_one_backwards_step_active",
                    "space_marines_not_one_backwards_step_objective_control_multiplier",
                    "space_marines_not_one_backwards_step_movement_lock_mode",
                    "space_marines_not_one_backwards_step_turn_owner",
                    "space_marines_not_one_backwards_step_turn",
                    "space_marines_not_one_backwards_step_source",
                ):
                    sr.pop(key, None)
            root.special_rules = sr

    def _queue_space_marines_bastion_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_bastion_task_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if phase_key == "SHOOTING_PHASE" and player is self.player and active_player is self.player:
            shooting_candidates = self._space_marines_bastion_phase_start_candidates(phase_key="shooting phase")
            heresy_candidates = self._space_marines_bastion_heresy_undone_candidates(phase_key="shooting phase")
            for stratagem_name, candidates in (
                ("CODEX DISCIPLINE", shooting_candidates),
                ("LIGHT OF VENGEANCE", shooting_candidates),
                ("HERESY UNDONE", heresy_candidates),
            ):
                stratagem = self.get_by_name(stratagem_name)
                if stratagem is None or not candidates:
                    continue
                if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
                    continue
                if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                if self._sm_reaction_already_queued(
                    event_name="phase_start",
                    stratagem_name=stratagem.name,
                    phase_name="Shooting phase",
                ):
                    continue
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

        if phase_key == "CHARGE_PHASE" and player is self.player and active_player is self.player:
            stratagem = self.get_by_name("HERESY UNDONE")
            candidates = self._space_marines_bastion_heresy_undone_candidates(phase_key="charge phase")
            if stratagem is not None and candidates:
                if (
                    int(getattr(self.player, "command_points", 0) or 0) >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                    and not self._sm_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Charge phase",
                    )
                ):
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

        if phase_key == "FIGHT_PHASE":
            candidates = self._space_marines_bastion_phase_start_candidates(phase_key="fight phase")
            if not candidates:
                return
            for stratagem_name in ("CODEX DISCIPLINE", "LIGHT OF VENGEANCE"):
                stratagem = self.get_by_name(stratagem_name)
                if stratagem is None:
                    continue
                if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
                    continue
                if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                if self._sm_reaction_already_queued(
                    event_name="phase_start",
                    stratagem_name=stratagem.name,
                    phase_name="Fight phase",
                ):
                    continue
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

    def _queue_space_marines_bastion_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any,
    ) -> None:
        if not self._is_bastion_task_force_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        source_unit = self._space_marines_bastion_post_attack_source(
            attacker_unit=attacker_unit,
            hits_by_target=hits_by_target,
        )
        if source_unit is None:
            return
        self._queue_space_marines_bastion_post_attack_reactions(
            event_name="unit_shooting_resolved",
            phase_name="Shooting phase",
            source_unit=source_unit,
        )

    def _capture_space_marines_bastion_fight_attacks_resolved(self, *, unit: Any, hits_by_target: Any) -> None:
        if not self._is_bastion_task_force_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        source_unit = self._space_marines_bastion_post_attack_source(
            attacker_unit=unit,
            hits_by_target=hits_by_target,
        )
        if source_unit is None:
            return
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_bastion_post_fight_ready"] = True
        sr["space_marines_bastion_post_fight_ready_owner"] = owner_id
        sr["space_marines_bastion_post_fight_ready_turn"] = int(turn or 0)
        source_unit.special_rules = sr

    def _queue_space_marines_bastion_fight_sequence_complete_reactions(self, *, unit: Any) -> None:
        if not self._is_bastion_task_force_detachment():
            return
        if unit is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        source_unit = self._sm_root(unit)
        if source_unit is None:
            return
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        ready = bool(sr.get("space_marines_bastion_post_fight_ready", False))
        ready_owner = str(sr.get("space_marines_bastion_post_fight_ready_owner", "") or "")
        try:
            ready_turn = int(sr.get("space_marines_bastion_post_fight_ready_turn", 0) or 0)
        except Exception:
            ready_turn = 0
        for key in (
            "space_marines_bastion_post_fight_ready",
            "space_marines_bastion_post_fight_ready_owner",
            "space_marines_bastion_post_fight_ready_turn",
        ):
            sr.pop(key, None)
        source_unit.special_rules = sr
        if not ready:
            return
        if owner_id and ready_owner and owner_id != ready_owner:
            return
        if turn and ready_turn and turn != ready_turn:
            return
        if not self._sm_owned_by_player(source_unit, self.player):
            return
        if not self._sm_on_battlefield(source_unit, require_targetable=True):
            return
        if not self._is_adeptus_astartes_unit(source_unit):
            return
        if not self._sm_is_battleline_unit(source_unit):
            return
        self._queue_space_marines_bastion_post_attack_reactions(
            event_name="fight_sequence_complete",
            phase_name="Fight phase",
            source_unit=source_unit,
        )

    def _cleanup_space_marines_bastion_phase_end_effects(self, *, player: Any, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
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
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE", "CHARGE_PHASE"}:
                prefix_map = {
                    "space_marines_bastion_codex_discipline": {"SHOOTING_PHASE", "FIGHT_PHASE"},
                    "space_marines_bastion_light_of_vengeance": {"SHOOTING_PHASE", "FIGHT_PHASE"},
                    "space_marines_bastion_heresy_undone": {"SHOOTING_PHASE", "CHARGE_PHASE"},
                }
                for prefix, phases in prefix_map.items():
                    if phase_key not in phases:
                        continue
                    for key in (
                        f"{prefix}_active",
                        f"{prefix}_choice",
                        f"{prefix}_turn_owner",
                        f"{prefix}_turn",
                        f"{prefix}_expires_phase",
                        f"{prefix}_source",
                    ):
                        sr.pop(key, None)
            if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                for key in (
                    "interlocking_tactics_last_scan_target_id",
                    "interlocking_tactics_last_scan_owner",
                    "interlocking_tactics_last_scan_turn",
                    "interlocking_tactics_last_scan_phase",
                    "space_marines_bastion_post_fight_ready",
                    "space_marines_bastion_post_fight_ready_owner",
                    "space_marines_bastion_post_fight_ready_turn",
                ):
                    sr.pop(key, None)
                for prefix in (
                    "space_marines_bastion_guided_disruption",
                    "space_marines_bastion_shock_bombardment",
                ):
                    for key in (
                        f"{prefix}_pending",
                        f"{prefix}_pending_turn_owner",
                        f"{prefix}_pending_turn",
                        f"{prefix}_pending_phase",
                        f"{prefix}_source",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _space_marines_black_spear_adaptive_tactics_candidates(self) -> tuple[list[Any], list[Any]]:
        if not self._is_black_spear_task_force_detachment():
            return ([], [])
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return ([], [])
        out: list[Any] = []
        kill_team_out: list[Any] = []
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
            out.append(root)
            if self._sm_is_kill_team_unit(root):
                kill_team_out.append(root)
        return (sorted(out, key=self._sm_sort_key), sorted(kill_team_out, key=self._sm_sort_key))

    def _space_marines_black_spear_special_issue_ammunition_candidates(self) -> list[Any]:
        if not self._is_black_spear_task_force_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._sm_detachment_mgr()
        out: list[Any] = []
        seen: set[str] = set()
        game = getattr(self.player, "game", None)
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
            if not self._sm_is_kill_team_unit(root):
                continue
            if self._sm_selected_to_shoot_this_phase(root):
                continue
            ammo_mode = ("", "")
            if mgr is not None:
                getter = getattr(mgr, "black_spear_special_issue_ammunition_mode", None)
                if callable(getter):
                    ammo_mode = getter(root, game=game)
            if str(ammo_mode[0] or "").strip():
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _space_marines_black_spear_site_to_site_candidates(self) -> tuple[list[Any], list[Any]]:
        if not self._is_black_spear_task_force_detachment():
            return ([], [])
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return ([], [])
        out: list[Any] = []
        kill_team_out: list[Any] = []
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
            if self._sm_unit_is_engaged(root):
                continue
            is_kill_team = self._sm_is_kill_team_unit(root)
            if not is_kill_team and not self._sm_is_infantry_unit(root):
                continue
            out.append(root)
            if is_kill_team:
                kill_team_out.append(root)
        return (sorted(out, key=self._sm_sort_key), sorted(kill_team_out, key=self._sm_sort_key))

    def _queue_space_marines_black_spear_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_black_spear_task_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if phase_key == "COMMAND_PHASE" and player is self.player and active_player is self.player:
            stratagem = self.get_by_name("ADAPTIVE TACTICS")
            candidates, kill_team_candidates = self._space_marines_black_spear_adaptive_tactics_candidates()
            if stratagem is not None and candidates:
                if (
                    int(getattr(self.player, "command_points", 0) or 0) >= self._sm_effective_cp_cost(self.player, stratagem)
                    and str(stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
                    and not self._sm_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Command phase",
                    )
                ):
                    payload = {
                        "event": "phase_start",
                        "phase": "Command phase",
                        "phase_name": "Command phase",
                        "stratagem": stratagem.name,
                        "cp_cost": stratagem.cp_cost,
                        "candidates": candidates,
                        "kill_team_candidates": kill_team_candidates,
                        "max_units": 2 if len(kill_team_candidates) >= 2 else 1,
                        "mission_tactic_options": self._sm_black_spear_mission_tactic_options(),
                    }
                    if len(candidates) == 1:
                        payload["unit"] = candidates[0]
                        payload["target_unit"] = candidates[0]
                    self._queue_reaction(payload, use_timer=False)

        if phase_key == "SHOOTING_PHASE" and player is self.player and active_player is self.player:
            candidates = self._space_marines_black_spear_special_issue_ammunition_candidates()
            if not candidates:
                return
            for stratagem_name in ("DRAGONFIRE ROUNDS", "HELLFIRE ROUNDS", "KRAKEN ROUNDS"):
                stratagem = self.get_by_name(stratagem_name)
                if stratagem is None:
                    continue
                if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
                    continue
                if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
                    continue
                if self._sm_reaction_already_queued(
                    event_name="phase_start",
                    stratagem_name=stratagem.name,
                    phase_name="Shooting phase",
                ):
                    continue
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

    def _queue_space_marines_black_spear_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_black_spear_task_force_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE" or player is self.player:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        stratagem = self.get_by_name("SITE-TO-SITE TELEPORTATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < self._sm_effective_cp_cost(self.player, stratagem):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates, kill_team_candidates = self._space_marines_black_spear_site_to_site_candidates()
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
            "kill_team_candidates": kill_team_candidates,
            "max_units": 2 if len(kill_team_candidates) >= 2 else 1,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_space_marines_black_spear_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        mgr = self._sm_detachment_mgr()
        if mgr is None:
            return
        clear_fn = getattr(mgr, "clear_black_spear_special_issue_ammunition", None)
        if not callable(clear_fn):
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
            clear_fn(root)

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
                if phase_name == "SHOOTING_PHASE":
                    exp = str(sr.get("space_marines_in_the_shadow_expires_phase", "") or "").strip().upper()
                    if sr.get("space_marines_in_the_shadow_active") is True and (not exp or exp == phase_name):
                        for key in (
                            "space_marines_in_the_shadow_active",
                            "space_marines_in_the_shadow_targeting_range",
                            "space_marines_in_the_shadow_expires_phase",
                            "space_marines_in_the_shadow_turn_owner",
                            "space_marines_in_the_shadow_turn",
                            "space_marines_in_the_shadow_source",
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

    def _use_space_marines_black_spear_task_force_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_black_spear_task_force_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "ADAPTIVE TACTICS":
            return self._use_space_marines_adaptive_tactics(stratagem, **kwargs)
        if name_u == "DRAGONFIRE ROUNDS":
            return self._use_space_marines_dragonfire_rounds(stratagem, **kwargs)
        if name_u == "HELLFIRE ROUNDS":
            return self._use_space_marines_hellfire_rounds(stratagem, **kwargs)
        if name_u == "KRAKEN ROUNDS":
            return self._use_space_marines_kraken_rounds(stratagem, **kwargs)
        if name_u == "SITE-TO-SITE TELEPORTATION":
            return self._use_space_marines_site_to_site_teleportation(stratagem, **kwargs)
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

    def _use_space_marines_angelic_inheritors_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_angelic_inheritors_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "FOCUSED FURY":
            return self._use_space_marines_focused_fury(stratagem, **kwargs)
        if name_u == "IN THE SHADOW OF GREAT WINGS":
            return self._use_space_marines_in_the_shadow_of_great_wings(stratagem, **kwargs)
        if name_u == "INSTANT OF GRACE":
            return self._use_space_marines_instant_of_grace(stratagem, **kwargs)
        if name_u == "STRIKE NOW FOR GLORY":
            return self._use_space_marines_strike_now_for_glory(stratagem, **kwargs)
        if name_u == "UNTO THE BURNING SKIES":
            return self._use_space_marines_unto_the_burning_skies(stratagem, **kwargs)
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

    def _use_space_marines_anvil_siege_force_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_anvil_siege_force_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "BATTLE DRILL RECALL":
            return self._use_space_marines_battle_drill_recall(stratagem, **kwargs)
        if name_u == "NO THREAT TOO GREAT":
            return self._use_space_marines_no_threat_too_great(stratagem, **kwargs)
        if name_u == "NOT ONE BACKWARDS STEP":
            return self._use_space_marines_not_one_backwards_step(stratagem, **kwargs)
        if name_u == "HAIL OF VENGEANCE":
            return self._use_space_marines_hail_of_vengeance(stratagem, **kwargs)
        if name_u == "RIGID DISCIPLINE":
            return self._use_space_marines_rigid_discipline(stratagem, **kwargs)
        return None

    def _use_space_marines_bastion_task_force_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_bastion_task_force_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "CODEX DISCIPLINE":
            return self._use_space_marines_codex_discipline(stratagem, **kwargs)
        if name_u == "GUIDED DISRUPTION":
            return self._use_space_marines_guided_disruption(stratagem, **kwargs)
        if name_u == "HERESY UNDONE":
            return self._use_space_marines_heresy_undone(stratagem, **kwargs)
        if name_u == "LIGHT OF VENGEANCE":
            return self._use_space_marines_light_of_vengeance(stratagem, **kwargs)
        if name_u == "SHOCK BOMBARDMENT":
            return self._use_space_marines_shock_bombardment(stratagem, **kwargs)
        return None

    def _sm_bastion_context(self, stratagem_name: str, kwargs: dict[str, Any]) -> tuple[Any, list[Any], bool]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            from_pending = True
            if unit is None:
                unit = reaction.get("unit") or reaction.get("target_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not kwargs.get("phase_name") and reaction.get("phase_name"):
                kwargs["phase_name"] = reaction.get("phase_name")
            break
        return unit, candidates, from_pending

    @staticmethod
    def _sm_bastion_light_choice(choice: Any) -> str:
        normalized = str(choice or "").strip().upper()
        normalized = normalized.replace(" ", "_")
        if normalized == "SUSTAINED":
            normalized = "SUSTAINED_HITS_1"
        if normalized == "LETHAL":
            normalized = "LETHAL_HITS"
        if normalized in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return normalized
        return ""

    def _sm_anvil_context(self, stratagem_name: str, kwargs: dict[str, Any]) -> tuple[Any, list[Any], Any, bool]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
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
            if attacking_unit is None:
                attacking_unit = reaction.get("attacking_unit") or reaction.get("attacker_unit") or reaction.get("enemy_unit")
            if not kwargs.get("phase_name") and reaction.get("phase_name"):
                kwargs["phase_name"] = reaction.get("phase_name")
            break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        return (unit, candidates, attacking_unit, from_pending)

    def _sm_angelic_context(
        self,
        stratagem_name: str,
        kwargs: dict[str, Any],
    ) -> tuple[Any, list[Any], Any, list[Any], Any, list[Any], bool]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
        target_units = list(kwargs.get("target_units") or [])
        target_model = kwargs.get("model") or kwargs.get("target_model")
        model_candidates = list(kwargs.get("model_candidates") or [])
        model_map = kwargs.get("model_candidates_by_unit")
        from_pending = False
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            from_pending = True
            if unit is None:
                unit = reaction.get("unit") or reaction.get("target_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit") or reaction.get("attacker_unit")
            if not target_units:
                target_units = list(reaction.get("target_units") or [])
            if target_model is None:
                target_model = reaction.get("model") or reaction.get("target_model")
            if not model_candidates:
                model_candidates = list(reaction.get("model_candidates") or [])
            if model_map is None:
                model_map = reaction.get("model_candidates_by_unit")
            if not kwargs.get("phase_name") and reaction.get("phase_name"):
                kwargs["phase_name"] = reaction.get("phase_name")
            break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        root = self._sm_root(unit)
        if root is not None and not model_candidates and hasattr(model_map, "get"):
            model_candidates = list(model_map.get(self._sm_sort_key(root)) or [])
        if target_model is None and len(model_candidates) == 1:
            target_model = model_candidates[0]
        return (unit, candidates, attacking_unit, target_units, target_model, model_candidates, from_pending)

    def _sm_black_spear_mission_tactic_options(self) -> list[dict[str, str]]:
        mgr = self._sm_detachment_mgr()
        if mgr is None:
            return []
        keys = list(getattr(mgr, "_MISSION_TACTIC_KEYS", ()) or ())
        label_fn = getattr(mgr, "mission_tactic_label", None)
        out: list[dict[str, str]] = []
        for key in list(keys or []):
            choice_key = str(key or "").strip().upper()
            if not choice_key:
                continue
            label = label_fn(choice_key) if callable(label_fn) else choice_key.title().replace("_", " ")
            out.append({"choice_key": choice_key, "label": str(label or choice_key)})
        return out

    def _sm_black_spear_mission_tactic_key(self, choice: Any) -> str:
        mgr = self._sm_detachment_mgr()
        if mgr is None:
            return ""
        normalize = getattr(mgr, "_normalize_mission_tactic_key", None)
        if not callable(normalize):
            return ""
        key = str(normalize(choice) or "").strip().upper()
        valid = set(getattr(mgr, "_MISSION_TACTIC_KEYS", ()) or ())
        if key not in valid:
            return ""
        return key

    def _sm_black_spear_special_issue_mode(self, choice: Any) -> str:
        mgr = self._sm_detachment_mgr()
        if mgr is None:
            return ""
        normalize = getattr(mgr, "_normalize_black_spear_special_issue_ammunition_mode", None)
        if not callable(normalize):
            return ""
        return str(normalize(choice) or "").strip().upper()

    def _sm_black_spear_choice_from_mapping(self, mapping: Any, root: Any) -> Any:
        if not isinstance(mapping, dict) or root is None:
            return None
        if root in mapping:
            return mapping[root]
        root_id = self._sm_sort_key(root)
        for key, value in list(mapping.items()):
            if key is root:
                return value
            key_id = ""
            if isinstance(key, str):
                key_id = str(key or "").strip()
            else:
                key_id = str(get_entity_id(key) or key or "").strip()
            if key_id and root_id and key_id == root_id:
                return value
        return None

    def _sm_black_spear_context(
        self,
        stratagem_name: str,
        kwargs: dict[str, Any],
    ) -> tuple[list[Any], list[Any], list[Any], int, Any, bool]:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        kill_team_candidates = list(kwargs.get("kill_team_candidates") or [])
        max_units = int(kwargs.get("max_units", 0) or 0)
        choice_payload = (
            kwargs.get("choices_by_unit")
            or kwargs.get("choice_by_unit")
            or kwargs.get("tactic_by_unit")
            or kwargs.get("mission_tactic_by_unit")
        )
        from_pending = False
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            from_pending = True
            if selected is None:
                selected = (
                    reaction.get("units")
                    or reaction.get("selected_units")
                    or reaction.get("target_units")
                    or reaction.get("unit")
                    or reaction.get("target_unit")
                )
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not kill_team_candidates:
                kill_team_candidates = list(reaction.get("kill_team_candidates") or [])
            if not max_units:
                max_units = int(reaction.get("max_units", 0) or 0)
            if choice_payload is None:
                choice_payload = (
                    reaction.get("choices_by_unit")
                    or reaction.get("choice_by_unit")
                    or reaction.get("tactic_by_unit")
                    or reaction.get("mission_tactic_by_unit")
                )
            if not kwargs.get("phase_name") and reaction.get("phase_name"):
                kwargs["phase_name"] = reaction.get("phase_name")
            break
        selected_roots = self._sm_resolve_units(selected)
        if not selected_roots and len(candidates) == 1:
            selected_roots = [self._sm_root(candidates[0])]
        selected_roots = [root for root in list(selected_roots or []) if root is not None]
        return (selected_roots, candidates, kill_team_candidates, int(max_units or 0), choice_payload, from_pending)

    def _use_space_marines_focused_fury(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: FOCUSED FURY: wrong phase")
            return False
        unit, candidates, _attacking_unit, _target_units, _target_model, _model_candidates, _from_pending = self._sm_angelic_context(
            "FOCUSED FURY",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: FOCUSED FURY: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: FOCUSED FURY: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: FOCUSED FURY: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: FOCUSED FURY: target must be an ADEPTUS ASTARTES unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: FOCUSED FURY: selected unit is not currently eligible")
            return False
        if self._sm_selected_to_fight_this_phase(root):
            logger.error("ERROR: FOCUSED FURY: target has already been selected to fight this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        source = str(getattr(stratagem, "name", "") or "FOCUSED FURY")
        bonus_keywords = ["LETHAL HITS"]
        if self._sm_is_character_unit(root):
            bonus_keywords.append("LANCE")
        for model in self._sm_unit_models(root):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or "")
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_melee = getattr(wargear, "is_melee", None)
                if not callable(is_melee) or not bool(is_melee()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=f"space_marines_focused_fury:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=list(bonus_keywords),
                        source=source,
                        expires_phase="FIGHT_PHASE",
                        attack_type="melee",
                    )

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FOCUSED FURY: %s gains [LETHAL HITS]%s on melee weapons this phase.",
            getattr(root, "name", "Unit"),
            " and [LANCE]" if "LANCE" in bonus_keywords else "",
        )
        return True

    def _use_space_marines_in_the_shadow_of_great_wings(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: not opponent's Shooting phase")
            return False
        unit, candidates, attacking_unit, target_units, _target_model, _model_candidates, from_pending = self._sm_angelic_context(
            "IN THE SHADOW OF GREAT WINGS",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        attacking_root = self._sm_root(attacking_unit)
        if attacking_root is not None and self._sm_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: attacking unit is not an enemy unit")
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_character_unit(root):
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: target must be a CHARACTER unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: selected unit is not currently eligible")
            return False
        if not from_pending and target_units and not any(self._sm_root(target) is root for target in list(target_units or [])):
            logger.error("ERROR: IN THE SHADOW OF GREAT WINGS: target unit was not selected as a shooting target")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_in_the_shadow_active"] = True
        sr["space_marines_in_the_shadow_targeting_range"] = 18
        sr["space_marines_in_the_shadow_expires_phase"] = "SHOOTING_PHASE"
        sr["space_marines_in_the_shadow_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_in_the_shadow_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_in_the_shadow_source"] = str(getattr(stratagem, "name", "") or "IN THE SHADOW OF GREAT WINGS")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: IN THE SHADOW OF GREAT WINGS: %s can only be targeted by ranged attacks from within 18\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_instant_of_grace(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: INSTANT OF GRACE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INSTANT OF GRACE: not your Command phase")
            return False
        unit, candidates, _attacking_unit, _target_units, target_model, model_candidates, _from_pending = self._sm_angelic_context(
            "INSTANT OF GRACE",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: INSTANT OF GRACE: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: INSTANT OF GRACE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: INSTANT OF GRACE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: INSTANT OF GRACE: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_infantry_unit(root):
            logger.error("ERROR: INSTANT OF GRACE: target must be an INFANTRY unit")
            return False
        valid_candidates, model_map = self._space_marines_angelic_instant_of_grace_candidates()
        if valid_candidates and root not in valid_candidates:
            logger.error("ERROR: INSTANT OF GRACE: selected unit is not currently eligible")
            return False
        if not model_candidates:
            model_candidates = list(model_map.get(self._sm_sort_key(root)) or [])
        if not model_candidates:
            logger.error("ERROR: INSTANT OF GRACE: no eligible non-CHARACTER model in target unit")
            return False
        selected_model = self._sm_resolve_selected_model(target_model, model_candidates)
        if selected_model is None:
            selected_model = model_candidates[0]
        if selected_model not in model_candidates:
            logger.error("ERROR: INSTANT OF GRACE: selected model is not currently eligible")
            return False
        if self._sm_model_is_character(selected_model):
            logger.error("ERROR: INSTANT OF GRACE: selected model must not already have the CHARACTER keyword")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        current_keywords = list(getattr(selected_model, "keywords", []) or [])
        current_keywords.append("CHARACTER")
        selected_model.keywords = current_keywords

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        added_unit_character = False
        already_character = self._sm_is_character_unit(root)
        if not already_character:
            added_keywords = list(sr.get("ability_added_keywords", []) or [])
            if not any(str(keyword or "").strip().upper() == "CHARACTER" for keyword in added_keywords):
                added_keywords.append("CHARACTER")
            sr["ability_added_keywords"] = added_keywords
            added_unit_character = True
        sr["space_marines_instant_of_grace_active"] = True
        sr["space_marines_instant_of_grace_model_id"] = str(get_entity_id(selected_model) or "")
        sr["space_marines_instant_of_grace_due_turn"] = int(getattr(self.game, "turn", 0) or 0) + 1 if self.game is not None else 0
        sr["space_marines_instant_of_grace_due_player_id"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_instant_of_grace_added_model_character"] = True
        sr["space_marines_instant_of_grace_added_unit_character"] = bool(added_unit_character)
        sr["space_marines_instant_of_grace_source"] = str(getattr(stratagem, "name", "") or "INSTANT OF GRACE")
        sr["space_marines_instant_of_grace_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_instant_of_grace_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        root.special_rules = sr
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INSTANT OF GRACE: %s in %s gains the CHARACTER keyword until your next Command phase.",
            getattr(selected_model, "name", "Model"),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_strike_now_for_glory(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: STRIKE NOW FOR GLORY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: STRIKE NOW FOR GLORY: not your Shooting phase")
            return False
        unit, candidates, _attacking_unit, _target_units, _target_model, _model_candidates, _from_pending = self._sm_angelic_context(
            "STRIKE NOW FOR GLORY",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: STRIKE NOW FOR GLORY: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: STRIKE NOW FOR GLORY: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: STRIKE NOW FOR GLORY: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: STRIKE NOW FOR GLORY: target must be an ADEPTUS ASTARTES unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: STRIKE NOW FOR GLORY: selected unit is not currently eligible")
            return False
        if self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: STRIKE NOW FOR GLORY: target has already been selected to shoot this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        source = str(getattr(stratagem, "name", "") or "STRIKE NOW FOR GLORY")
        for model in self._sm_unit_models(root):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or "")
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=f"space_marines_strike_now_for_glory:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["SUSTAINED HITS 1"],
                        source=source,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STRIKE NOW FOR GLORY: %s gains [SUSTAINED HITS 1] on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_unto_the_burning_skies(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: UNTO THE BURNING SKIES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: UNTO THE BURNING SKIES: not opponent's Fight phase")
            return False
        unit, candidates, _attacking_unit, _target_units, _target_model, _model_candidates, _from_pending = self._sm_angelic_context(
            "UNTO THE BURNING SKIES",
            kwargs,
        )
        if unit is None:
            logger.error("ERROR: UNTO THE BURNING SKIES: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: UNTO THE BURNING SKIES: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: UNTO THE BURNING SKIES: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: UNTO THE BURNING SKIES: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_jump_pack_unit(root):
            logger.error("ERROR: UNTO THE BURNING SKIES: target must be a JUMP PACK unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: UNTO THE BURNING SKIES: selected unit is not currently eligible")
            return False
        if self._sm_unit_is_engaged(root) and not self._sm_is_the_sanguinor(root):
            logger.error("ERROR: UNTO THE BURNING SKIES: target cannot be within Engagement Range unless it is The Sanguinor")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False
        if not self._sm_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "UNTO THE BURNING SKIES")):
            return False

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNTO THE BURNING SKIES: %s enters Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

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

    def _use_space_marines_adaptive_tactics(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: ADAPTIVE TACTICS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ADAPTIVE TACTICS: not your Command phase")
            return False

        selected_roots, candidates, kill_team_candidates, max_units, choice_payload, _from_pending = self._sm_black_spear_context(
            "ADAPTIVE TACTICS",
            kwargs,
        )
        if not selected_roots:
            logger.error("ERROR: ADAPTIVE TACTICS: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: ADAPTIVE TACTICS: cannot target more than two units")
            return False
        if int(max_units or 0) > 0 and len(selected_roots) > int(max_units):
            logger.error("ERROR: ADAPTIVE TACTICS: selected too many units")
            return False

        eligible, kill_team_eligible = self._space_marines_black_spear_adaptive_tactics_candidates()
        if candidates:
            eligible = candidates
        if kill_team_candidates:
            kill_team_eligible = kill_team_candidates
        for root in list(selected_roots):
            if not self._sm_owned_by_player(root, self.player):
                logger.error("ERROR: ADAPTIVE TACTICS: target unit is not yours")
                return False
            if not self._sm_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: ADAPTIVE TACTICS: target must be on the battlefield and targetable")
                return False
            if not self._is_adeptus_astartes_unit(root):
                logger.error("ERROR: ADAPTIVE TACTICS: target must be an ADEPTUS ASTARTES unit")
                return False
            if eligible and not self._sm_unit_in_candidates(root, eligible):
                logger.error("ERROR: ADAPTIVE TACTICS: one or more selected units are not currently eligible")
                return False
        if len(selected_roots) == 2 and not all(self._sm_unit_in_candidates(root, kill_team_eligible) for root in list(selected_roots)):
            logger.error("ERROR: ADAPTIVE TACTICS: selecting two units requires both units to be Kill Team units")
            return False

        choice_list = list(choice_payload or []) if isinstance(choice_payload, (list, tuple)) else []
        single_choice = (
            kwargs.get("choice")
            or kwargs.get("choice_key")
            or kwargs.get("mission_tactic")
            or kwargs.get("tactic")
            or kwargs.get("mode")
            or kwargs.get("selection")
        )
        normalized_choices: list[tuple[Any, str]] = []
        for index, root in enumerate(list(selected_roots or [])):
            raw_choice = self._sm_black_spear_choice_from_mapping(choice_payload, root)
            if raw_choice is None and index < len(choice_list):
                raw_choice = choice_list[index]
            if raw_choice is None and len(selected_roots) == 1:
                raw_choice = single_choice
            choice_key = self._sm_black_spear_mission_tactic_key(raw_choice)
            if not choice_key:
                logger.error("ERROR: ADAPTIVE TACTICS: each selected unit requires a valid Mission Tactic choice")
                return False
            normalized_choices.append((root, choice_key))

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Command phase"):
            logger.error("ERROR: ADAPTIVE TACTICS: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=first):
            return False

        mgr = self._sm_detachment_mgr()
        apply_fn = getattr(mgr, "set_black_spear_adaptive_tactics_for_unit", None) if mgr is not None else None
        label_fn = getattr(mgr, "mission_tactic_label", None) if mgr is not None else None
        if not callable(apply_fn):
            logger.error("ERROR: ADAPTIVE TACTICS: Black Spear detachment manager unavailable")
            return False
        battle_round = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or "")
        labels: list[str] = []
        for root, choice_key in list(normalized_choices or []):
            applied = apply_fn(
                root,
                choice_key,
                battle_round=battle_round,
                player_id=owner_id,
                source=str(getattr(stratagem, "name", "") or "ADAPTIVE TACTICS"),
            )
            if not bool(applied):
                logger.error("ERROR: ADAPTIVE TACTICS: failed to apply selected Mission Tactic")
                return False
            label = label_fn(choice_key) if callable(label_fn) else choice_key.title().replace("_", " ")
            labels.append(f"{getattr(root, 'name', 'Unit')}={label}")

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ADAPTIVE TACTICS: %s.", ", ".join(labels))
        return True

    def _use_space_marines_special_issue_ammunition(self, stratagem: Any, *, mode: str, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: %s: wrong phase", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: %s: not your Shooting phase", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False

        selected_roots, candidates, _kill_team_candidates, _max_units, _choice_payload, _from_pending = self._sm_black_spear_context(
            str(getattr(stratagem, "name", "") or ""),
            kwargs,
        )
        if not selected_roots:
            logger.error("ERROR: %s: no target unit provided", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        if len(selected_roots) != 1:
            logger.error("ERROR: %s: must target exactly one unit", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        root = selected_roots[0]
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: %s: target unit is not yours", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: %s: target must be on the battlefield and targetable", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: %s: target must be an ADEPTUS ASTARTES unit", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        if not self._sm_is_kill_team_unit(root):
            logger.error("ERROR: %s: target must be a Kill Team unit", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        if self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: %s: target has already been selected to shoot this phase", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False

        eligible = candidates or self._space_marines_black_spear_special_issue_ammunition_candidates()
        if eligible and not self._sm_unit_in_candidates(root, eligible):
            logger.error("ERROR: %s: selected unit is not currently eligible", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False

        mgr = self._sm_detachment_mgr()
        active_mode_fn = getattr(mgr, "black_spear_special_issue_ammunition_mode", None) if mgr is not None else None
        if callable(active_mode_fn):
            active_mode, _source = active_mode_fn(root, game=self.game)
            if str(active_mode or "").strip():
                logger.error("ERROR: %s: target unit already has Special-Issue Ammunition this phase", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
                return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: %s: cannot be used in current state", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        apply_fn = getattr(mgr, "set_black_spear_special_issue_ammunition", None) if mgr is not None else None
        if not callable(apply_fn):
            logger.error("ERROR: %s: Black Spear detachment manager unavailable", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False
        battle_round = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or "")
        applied = apply_fn(
            root,
            mode,
            battle_round=battle_round,
            player_id=owner_id,
            source=str(getattr(stratagem, "name", "") or mode),
        )
        if not bool(applied):
            logger.error("ERROR: %s: failed to apply Special-Issue Ammunition", getattr(stratagem, "name", "BLACK SPEAR AMMUNITION"))
            return False

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_space_marines_dragonfire_rounds(self, stratagem: Any, **kwargs) -> bool:
        selected_roots, _candidates, _kill_team_candidates, _max_units, _choice_payload, _from_pending = self._sm_black_spear_context(
            "DRAGONFIRE ROUNDS",
            kwargs,
        )
        ok = self._use_space_marines_special_issue_ammunition(
            stratagem,
            mode="DRAGONFIRE_ROUNDS",
            **kwargs,
        )
        if ok:
            root = selected_roots[0] if selected_roots else None
            logger.info(
                "INFO: DRAGONFIRE ROUNDS: %s gains [ASSAULT] and [IGNORES COVER] on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        return ok

    def _use_space_marines_hellfire_rounds(self, stratagem: Any, **kwargs) -> bool:
        selected_roots, _candidates, _kill_team_candidates, _max_units, _choice_payload, _from_pending = self._sm_black_spear_context(
            "HELLFIRE ROUNDS",
            kwargs,
        )
        ok = self._use_space_marines_special_issue_ammunition(
            stratagem,
            mode="HELLFIRE_ROUNDS",
            **kwargs,
        )
        if ok:
            root = selected_roots[0] if selected_roots else None
            logger.info(
                "INFO: HELLFIRE ROUNDS: %s gains [ANTI-INFANTRY 2+] and [ANTI-MONSTER 5+] on non-[DEVASTATING WOUNDS] ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        return ok

    def _use_space_marines_kraken_rounds(self, stratagem: Any, **kwargs) -> bool:
        selected_roots, _candidates, _kill_team_candidates, _max_units, _choice_payload, _from_pending = self._sm_black_spear_context(
            "KRAKEN ROUNDS",
            kwargs,
        )
        ok = self._use_space_marines_special_issue_ammunition(
            stratagem,
            mode="KRAKEN_ROUNDS",
            **kwargs,
        )
        if ok:
            root = selected_roots[0] if selected_roots else None
            logger.info(
                "INFO: KRAKEN ROUNDS: %s improves ranged AP by 1 and range by 6\" this phase.",
                getattr(root, "name", "Unit"),
            )
        return ok

    def _use_space_marines_site_to_site_teleportation(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: not opponent's Fight phase")
            return False

        selected_roots, candidates, kill_team_candidates, max_units, _choice_payload, _from_pending = self._sm_black_spear_context(
            "SITE-TO-SITE TELEPORTATION",
            kwargs,
        )
        if not selected_roots:
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: cannot target more than two units")
            return False
        if int(max_units or 0) > 0 and len(selected_roots) > int(max_units):
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: selected too many units")
            return False

        eligible, kill_team_eligible = self._space_marines_black_spear_site_to_site_candidates()
        if candidates:
            eligible = candidates
        if kill_team_candidates:
            kill_team_eligible = kill_team_candidates
        for root in list(selected_roots):
            if not self._sm_owned_by_player(root, self.player):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: target unit is not yours")
                return False
            if not self._sm_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: target must be on the battlefield and targetable")
                return False
            if not self._is_adeptus_astartes_unit(root):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: target must be an ADEPTUS ASTARTES unit")
                return False
            if self._sm_unit_is_engaged(root):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: target cannot be within Engagement Range")
                return False
            if eligible and not self._sm_unit_in_candidates(root, eligible):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: one or more selected units are not currently eligible")
                return False
        if len(selected_roots) == 2 and not all(self._sm_unit_in_candidates(root, kill_team_eligible) for root in list(selected_roots)):
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: selecting two units requires both units to be Kill Team units")
            return False
        if len(selected_roots) == 1 and not self._sm_unit_in_candidates(selected_roots[0], kill_team_eligible):
            if not self._sm_is_infantry_unit(selected_roots[0]):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: single non-Kill Team selection must be an INFANTRY unit")
                return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Fight phase"):
            logger.error("ERROR: SITE-TO-SITE TELEPORTATION: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=first):
            return False

        arrival_turn = self._sm_next_owner_movement_phase_turn(self.player)
        source_name = str(getattr(stratagem, "name", "") or "SITE-TO-SITE TELEPORTATION")
        owner_id = str(getattr(self.player, "id", "") or "")
        for root in list(selected_roots):
            if not self._sm_place_unit_into_strategic_reserves(root, reason=source_name):
                logger.error("ERROR: SITE-TO-SITE TELEPORTATION: failed to place target into Strategic Reserves")
                return False
            get_members = getattr(root, "get_attached_unit_members", None)
            members = list(get_members() or []) if callable(get_members) else [root]
            if not members:
                members = [root]
            for member in list(members or []):
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["midgame_temp_deep_strike"] = True
                sr["midgame_temp_deep_strike_turn_owner"] = owner_id
                sr["midgame_temp_deep_strike_must_arrive_turn"] = int(arrival_turn)
                sr["midgame_temp_deep_strike_source"] = source_name
                member.special_rules = sr
                self._sm_clear_ability_cache(member, "deep_strike")

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SITE-TO-SITE TELEPORTATION: %d unit(s) enter Strategic Reserves and return next Movement phase via Deep Strike.",
            len(selected_roots),
        )
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

    def _use_space_marines_battle_drill_recall(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: BATTLE DRILL RECALL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BATTLE DRILL RECALL: not your Shooting phase")
            return False

        unit, candidates, _attacking_unit, _from_pending = self._sm_anvil_context("BATTLE DRILL RECALL", kwargs)
        if unit is None:
            logger.error("ERROR: BATTLE DRILL RECALL: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: BATTLE DRILL RECALL: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: BATTLE DRILL RECALL: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: BATTLE DRILL RECALL: target must be an ADEPTUS ASTARTES unit")
            return False
        eligible = candidates or self._space_marines_anvil_shooting_candidates()
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: BATTLE DRILL RECALL: selected unit is not currently eligible")
                return False
        if self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: BATTLE DRILL RECALL: target has already been selected to shoot this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        source = str(getattr(stratagem, "name", "") or "BATTLE DRILL RECALL")
        for model in self._sm_unit_models(root):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or "")
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=f"space_marines_battle_drill_recall:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["SUSTAINED HITS 1"],
                        source=source,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_battle_drill_recall_active"] = True
        if bool(getattr(getattr(root, "round_state", None), "remained_stationary_this_round", False)):
            sr["space_marines_battle_drill_recall_crit_hit_threshold"] = 5
        sr["space_marines_battle_drill_recall_expires_phase"] = "SHOOTING_PHASE"
        sr["space_marines_battle_drill_recall_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_battle_drill_recall_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_battle_drill_recall_source"] = source
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BATTLE DRILL RECALL: %s gains [SUSTAINED HITS 1]%s this phase.",
            getattr(root, "name", "Unit"),
            " and critical hits on 5+" if int(sr.get("space_marines_battle_drill_recall_crit_hit_threshold", 0) or 0) == 5 else "",
        )
        return True

    def _use_space_marines_no_threat_too_great(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: NO THREAT TOO GREAT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NO THREAT TOO GREAT: not your Shooting phase")
            return False

        unit, candidates, _attacking_unit, _from_pending = self._sm_anvil_context("NO THREAT TOO GREAT", kwargs)
        if unit is None:
            logger.error("ERROR: NO THREAT TOO GREAT: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: NO THREAT TOO GREAT: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: NO THREAT TOO GREAT: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: NO THREAT TOO GREAT: target must be an ADEPTUS ASTARTES unit")
            return False
        eligible = candidates or self._space_marines_anvil_shooting_candidates()
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: NO THREAT TOO GREAT: selected unit is not currently eligible")
                return False
        if self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: NO THREAT TOO GREAT: target has already been selected to shoot this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_no_threat_too_great_active"] = True
        sr["space_marines_no_threat_too_great_expires_phase"] = "SHOOTING_PHASE"
        sr["space_marines_no_threat_too_great_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_no_threat_too_great_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_no_threat_too_great_source"] = str(getattr(stratagem, "name", "") or "NO THREAT TOO GREAT")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NO THREAT TOO GREAT: %s can re-roll ranged Wound rolls against MONSTER/VEHICLE units this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_not_one_backwards_step(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: NOT ONE BACKWARDS STEP: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NOT ONE BACKWARDS STEP: not your Command phase")
            return False

        unit, candidates, _attacking_unit, _from_pending = self._sm_anvil_context("NOT ONE BACKWARDS STEP", kwargs)
        if unit is None:
            logger.error("ERROR: NOT ONE BACKWARDS STEP: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: NOT ONE BACKWARDS STEP: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: NOT ONE BACKWARDS STEP: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: NOT ONE BACKWARDS STEP: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_infantry_unit(root):
            logger.error("ERROR: NOT ONE BACKWARDS STEP: target must be an INFANTRY unit")
            return False
        if not self._sm_unit_within_any_objective_range(root):
            logger.error("ERROR: NOT ONE BACKWARDS STEP: target must be within range of an objective marker")
            return False
        eligible = candidates or self._space_marines_anvil_not_one_backwards_step_candidates()
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: NOT ONE BACKWARDS STEP: selected unit is not currently eligible")
                return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_not_one_backwards_step_active"] = True
        sr["space_marines_not_one_backwards_step_objective_control_multiplier"] = 2
        sr["space_marines_not_one_backwards_step_movement_lock_mode"] = "remain_stationary"
        sr["space_marines_not_one_backwards_step_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_not_one_backwards_step_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_not_one_backwards_step_source"] = str(getattr(stratagem, "name", "") or "NOT ONE BACKWARDS STEP")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NOT ONE BACKWARDS STEP: %s doubles Objective Control and must remain stationary this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_hail_of_vengeance(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: HAIL OF VENGEANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: HAIL OF VENGEANCE: not opponent's Shooting phase")
            return False

        unit, candidates, attacking_unit, from_pending = self._sm_anvil_context("HAIL OF VENGEANCE", kwargs)
        if unit is None:
            logger.error("ERROR: HAIL OF VENGEANCE: no target unit provided")
            return False
        root = self._sm_root(unit)
        attacker_root = self._sm_root(attacking_unit)
        if root is None or attacker_root is None:
            logger.error("ERROR: HAIL OF VENGEANCE: missing attacking unit context")
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: HAIL OF VENGEANCE: target unit is not yours")
            return False
        if self._sm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: HAIL OF VENGEANCE: attacking unit is not an enemy unit")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: HAIL OF VENGEANCE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: HAIL OF VENGEANCE: target must be an ADEPTUS ASTARTES unit")
            return False
        if candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in candidates):
                logger.error("ERROR: HAIL OF VENGEANCE: selected unit is not currently eligible")
                return False
        elif not from_pending:
            logger.error("ERROR: HAIL OF VENGEANCE: missing lost-model trigger context")
            return False

        setup_can_shoot = getattr(self.game, "_setup_reactive_can_shoot_target", None) if self.game is not None else None
        if not callable(setup_can_shoot) or not bool(setup_can_shoot(root, attacker_root)):
            logger.error("ERROR: HAIL OF VENGEANCE: target cannot shoot the attacking unit")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        request = None
        if self.game is not None:
            request = self.game._queue_setup_reactive_shooting_decision(
                player=self.player,
                unit=root,
                target_unit=attacker_root,
                source=str(getattr(stratagem, "name", "") or "HAIL OF VENGEANCE"),
            )
        if request is not None:
            request.context["hail_of_vengeance_flow"] = True
            request.context["hail_of_vengeance_source"] = str(getattr(stratagem, "name", "") or "HAIL OF VENGEANCE")
            request.context["hail_of_vengeance_enemy_unit_id"] = str(get_entity_id(attacker_root) or "")
            request.context["hail_of_vengeance_unit_id"] = str(get_entity_id(root) or "")

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HAIL OF VENGEANCE: %s can make a reactive shooting attack against %s.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Enemy Unit"),
        )
        return True

    def _use_space_marines_rigid_discipline(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: RIGID DISCIPLINE: wrong phase")
            return False

        unit, candidates, _attacking_unit, _from_pending = self._sm_anvil_context("RIGID DISCIPLINE", kwargs)
        if unit is None:
            logger.error("ERROR: RIGID DISCIPLINE: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: RIGID DISCIPLINE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: RIGID DISCIPLINE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: RIGID DISCIPLINE: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_unit_is_engaged(root):
            logger.error("ERROR: RIGID DISCIPLINE: target must be within Engagement Range of an enemy unit")
            return False
        eligible = candidates or self._space_marines_anvil_rigid_discipline_candidates()
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: RIGID DISCIPLINE: selected unit is not currently eligible")
                return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        request = None
        if self.game is not None:
            request = self.game._queue_reactive_move_movement_decision(
                player=self.player,
                unit=root,
                max_distance=6,
                kind="rigid_discipline",
                movement_type="fall_back",
                source=str(getattr(stratagem, "name", "") or "RIGID DISCIPLINE"),
            )
        if request is not None:
            request.context["rigid_discipline_flow"] = True
            request.context["rigid_discipline_source"] = str(getattr(stratagem, "name", "") or "RIGID DISCIPLINE")
            request.context["rigid_discipline_unit_id"] = str(get_entity_id(root) or "")

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RIGID DISCIPLINE: %s can make a Fall Back move of up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_codex_discipline(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: CODEX DISCIPLINE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: CODEX DISCIPLINE: not your Shooting phase")
            return False

        unit, candidates, _from_pending = self._sm_bastion_context("CODEX DISCIPLINE", kwargs)
        if unit is None:
            logger.error("ERROR: CODEX DISCIPLINE: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: CODEX DISCIPLINE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: CODEX DISCIPLINE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: CODEX DISCIPLINE: target must be an ADEPTUS ASTARTES unit")
            return False
        eligible = candidates or self._space_marines_bastion_phase_start_candidates(phase_key=phase_name)
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: CODEX DISCIPLINE: selected unit is not currently eligible")
                return False
        if phase_name == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: CODEX DISCIPLINE: target has already been selected to shoot this phase")
            return False
        if phase_name == "fight phase" and self._sm_selected_to_fight_this_phase(root):
            logger.error("ERROR: CODEX DISCIPLINE: target has already been selected to fight this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_bastion_codex_discipline_active"] = True
        sr["space_marines_bastion_codex_discipline_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_bastion_codex_discipline_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_bastion_codex_discipline_expires_phase"] = (
            "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        )
        sr["space_marines_bastion_codex_discipline_source"] = str(getattr(stratagem, "name", "") or "CODEX DISCIPLINE")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CODEX DISCIPLINE: %s re-rolls Hit rolls of 1, and re-rolls Wound rolls of 1 vs auspex scanned targets, this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_light_of_vengeance(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: LIGHT OF VENGEANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: LIGHT OF VENGEANCE: not your Shooting phase")
            return False

        choice = self._sm_bastion_light_choice(
            kwargs.get("choice")
            or kwargs.get("choice_key")
            or kwargs.get("mode")
            or kwargs.get("selection")
        )
        if not choice:
            logger.error("ERROR: LIGHT OF VENGEANCE: choice must be LETHAL_HITS or SUSTAINED_HITS_1")
            return False

        unit, candidates, _from_pending = self._sm_bastion_context("LIGHT OF VENGEANCE", kwargs)
        if unit is None:
            logger.error("ERROR: LIGHT OF VENGEANCE: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: LIGHT OF VENGEANCE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: LIGHT OF VENGEANCE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: LIGHT OF VENGEANCE: target must be an ADEPTUS ASTARTES unit")
            return False
        eligible = candidates or self._space_marines_bastion_phase_start_candidates(phase_key=phase_name)
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: LIGHT OF VENGEANCE: selected unit is not currently eligible")
                return False
        if phase_name == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: LIGHT OF VENGEANCE: target has already been selected to shoot this phase")
            return False
        if phase_name == "fight phase" and self._sm_selected_to_fight_this_phase(root):
            logger.error("ERROR: LIGHT OF VENGEANCE: target has already been selected to fight this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_bastion_light_of_vengeance_active"] = True
        sr["space_marines_bastion_light_of_vengeance_choice"] = choice
        sr["space_marines_bastion_light_of_vengeance_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_bastion_light_of_vengeance_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_bastion_light_of_vengeance_expires_phase"] = (
            "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        )
        sr["space_marines_bastion_light_of_vengeance_source"] = str(getattr(stratagem, "name", "") or "LIGHT OF VENGEANCE")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LIGHT OF VENGEANCE: %s gains %s while targeting auspex scanned units, or while it has BATTLELINE, this phase.",
            getattr(root, "name", "Unit"),
            "LETHAL HITS" if choice == "LETHAL_HITS" else "SUSTAINED HITS 1",
        )
        return True

    def _use_space_marines_heresy_undone(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "charge phase"}:
            logger.error("ERROR: HERESY UNDONE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: HERESY UNDONE: not your phase")
            return False

        unit, candidates, _from_pending = self._sm_bastion_context("HERESY UNDONE", kwargs)
        if unit is None:
            logger.error("ERROR: HERESY UNDONE: no target unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: HERESY UNDONE: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: HERESY UNDONE: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: HERESY UNDONE: target must be an ADEPTUS ASTARTES unit")
            return False
        if self._sm_is_battleline_unit(root):
            logger.error("ERROR: HERESY UNDONE: target cannot be a BATTLELINE unit")
            return False
        eligible = candidates or self._space_marines_bastion_heresy_undone_candidates(phase_key=phase_name)
        if eligible:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in eligible):
                logger.error("ERROR: HERESY UNDONE: selected unit is not currently eligible")
                return False
        if phase_name == "shooting phase" and self._sm_selected_to_shoot_this_phase(root):
            logger.error("ERROR: HERESY UNDONE: target has already been selected to shoot this phase")
            return False
        if phase_name == "charge phase" and self._sm_selected_to_charge_this_phase(root):
            logger.error("ERROR: HERESY UNDONE: target has already been selected to charge this phase")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["space_marines_bastion_heresy_undone_active"] = True
        sr["space_marines_bastion_heresy_undone_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["space_marines_bastion_heresy_undone_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["space_marines_bastion_heresy_undone_expires_phase"] = (
            "SHOOTING_PHASE" if phase_name == "shooting phase" else "CHARGE_PHASE"
        )
        sr["space_marines_bastion_heresy_undone_source"] = str(getattr(stratagem, "name", "") or "HERESY UNDONE")
        root.special_rules = sr

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HERESY UNDONE: %s can shoot or charge after Advancing or Falling Back this phase, but those targets must be auspex scanned if it does so.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_guided_disruption(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: GUIDED DISRUPTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: GUIDED DISRUPTION: not your Shooting phase")
            return False

        unit, candidates, from_pending = self._sm_bastion_context("GUIDED DISRUPTION", kwargs)
        if unit is None:
            logger.error("ERROR: GUIDED DISRUPTION: no source unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: GUIDED DISRUPTION: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: GUIDED DISRUPTION: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: GUIDED DISRUPTION: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_battleline_unit(root):
            logger.error("ERROR: GUIDED DISRUPTION: target must be a BATTLELINE unit")
            return False
        if candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in candidates):
                logger.error("ERROR: GUIDED DISRUPTION: selected unit is not currently eligible")
                return False
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        has_last_scan = self._sm_bastion_last_scan_target(
            root,
            owner_id=owner_id,
            turn=turn,
            phase_key=phase_key,
        ) is not None
        if not from_pending and not has_last_scan:
            logger.error("ERROR: GUIDED DISRUPTION: missing completed-attack trigger context")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "GUIDED DISRUPTION")
        self._sm_bastion_clear_pending_effect(root, prefix="space_marines_bastion_guided_disruption")
        if has_last_scan:
            self._sm_bastion_resolve_last_scan_effect(
                root=root,
                prefix="space_marines_bastion_guided_disruption",
                owner_id=owner_id,
                turn=turn,
                phase_key=phase_key,
                source_name=source_name,
            )
        else:
            self._sm_bastion_set_pending_effect(
                root,
                prefix="space_marines_bastion_guided_disruption",
                owner_id=owner_id,
                turn=turn,
                phase_key=phase_key,
                source_name=source_name,
            )

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GUIDED DISRUPTION: %s will pin the auspex scanned unit from its latest attack sequence if that target is not a MONSTER or VEHICLE.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_space_marines_shock_bombardment(self, stratagem: Any, **kwargs) -> bool:
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SHOCK BOMBARDMENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: SHOCK BOMBARDMENT: not your Shooting phase")
            return False

        unit, candidates, from_pending = self._sm_bastion_context("SHOCK BOMBARDMENT", kwargs)
        if unit is None:
            logger.error("ERROR: SHOCK BOMBARDMENT: no source unit provided")
            return False
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: SHOCK BOMBARDMENT: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SHOCK BOMBARDMENT: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: SHOCK BOMBARDMENT: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_battleline_unit(root):
            logger.error("ERROR: SHOCK BOMBARDMENT: target must be a BATTLELINE unit")
            return False
        if candidates:
            root_id = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != root_id for candidate in candidates):
                logger.error("ERROR: SHOCK BOMBARDMENT: selected unit is not currently eligible")
                return False
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        has_last_scan = self._sm_bastion_last_scan_target(
            root,
            owner_id=owner_id,
            turn=turn,
            phase_key=phase_key,
        ) is not None
        if not from_pending and not has_last_scan:
            logger.error("ERROR: SHOCK BOMBARDMENT: missing completed-attack trigger context")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "SHOCK BOMBARDMENT")
        self._sm_bastion_clear_pending_effect(root, prefix="space_marines_bastion_shock_bombardment")
        if has_last_scan:
            self._sm_bastion_resolve_last_scan_effect(
                root=root,
                prefix="space_marines_bastion_shock_bombardment",
                owner_id=owner_id,
                turn=turn,
                phase_key=phase_key,
                source_name=source_name,
            )
        else:
            self._sm_bastion_set_pending_effect(
                root,
                prefix="space_marines_bastion_shock_bombardment",
                owner_id=owner_id,
                turn=turn,
                phase_key=phase_key,
                source_name=source_name,
            )

        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHOCK BOMBARDMENT: %s will suppress the auspex scanned unit from its latest attack sequence.",
            getattr(root, "name", "Unit"),
        )
        return True
