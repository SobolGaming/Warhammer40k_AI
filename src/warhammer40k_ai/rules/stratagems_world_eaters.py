from __future__ import annotations

from typing import Any, List, Optional

from ..utility.entity_ids import get_entity_id


class WorldEatersStratagemMixin:
    @staticmethod
    def _goretrack_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                return get_root()
            except (AttributeError, TypeError, ValueError):
                return unit
        return unit

    @staticmethod
    def _goretrack_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _is_unit_alive(unit: Any) -> bool:
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            try:
                return bool(is_alive())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _is_unit_in_reserves(unit: Any) -> bool:
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves):
            try:
                return bool(in_reserves())
            except (AttributeError, TypeError, ValueError):
                return True
        return bool(in_reserves)

    def _is_stratagem_target_legal(self, unit: Any) -> bool:
        checker = getattr(self, "_unit_cannot_be_target_of_stratagem", None)
        if callable(checker):
            return not bool(checker(unit))
        return True

    def _get_world_eaters_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "world_eaters_detachments", None) if army is not None else None

    def _is_goretrack_onslaught(self) -> bool:
        mgr = self._get_world_eaters_mgr()
        checker = getattr(mgr, "is_goretrack_onslaught", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_world_eaters_unit(self, unit: Any, mgr=None) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if mgr is None:
            mgr = self._get_world_eaters_mgr()
        unit_is_we = getattr(mgr, "unit_is_world_eaters", None) if mgr is not None else None
        if callable(unit_is_we):
            return bool(unit_is_we(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword("WORLD EATERS"))
        return False

    def _goretrack_embarked_units(
        self,
        transport_unit: Any,
        *,
        require_world_eaters: bool = True,
        require_khorne_berzerkers: bool = False,
    ) -> List[Any]:
        if transport_unit is None:
            return []
        mgr = self._get_world_eaters_mgr()
        passengers = list(getattr(transport_unit, "transport_passengers", []) or [])
        candidates: List[Any] = []
        for passenger in passengers:
            root = self._goretrack_root(passenger)
            if root is None:
                continue
            if require_world_eaters and not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            if require_khorne_berzerkers:
                has_keyword = getattr(root, "has_keyword", None)
                if not callable(has_keyword):
                    continue
                try:
                    if not (has_keyword("KHORNE") and has_keyword("BERZERKERS")):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _goretrack_rhino_candidates(
        self,
        *,
        require_not_moved: bool = False,
        require_any_passengers: bool = False,
        require_khorne_berzerkers: bool = False,
    ) -> List[Any]:
        if not self._is_goretrack_onslaught():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_world_eaters_mgr()
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._goretrack_root(unit)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._is_unit_alive(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            if self._is_unit_in_reserves(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            has_keyword = getattr(root, "has_keyword", None)
            if not callable(has_keyword):
                continue
            try:
                if not has_keyword("RHINO"):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if require_not_moved:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "moved_this_round", False)):
                    continue
            if require_any_passengers or require_khorne_berzerkers:
                passengers = self._goretrack_embarked_units(
                    root,
                    require_world_eaters=True,
                    require_khorne_berzerkers=require_khorne_berzerkers,
                )
                if not passengers:
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _goretrack_vehicle_candidates(
        self,
        *,
        require_not_moved: bool = False,
    ) -> List[Any]:
        if not self._is_goretrack_onslaught():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_world_eaters_mgr()
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._goretrack_root(unit)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._is_unit_alive(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            if self._is_unit_in_reserves(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            has_keyword = getattr(root, "has_keyword", None)
            if callable(has_keyword):
                try:
                    is_vehicle = bool(has_keyword("VEHICLE"))
                except (AttributeError, TypeError, ValueError):
                    is_vehicle = False
            else:
                is_vehicle = False
            if not (is_vehicle or bool(getattr(root, "is_vehicle", False))):
                continue
            if require_not_moved:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "moved_this_round", False)):
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _goretrack_endless_pursuit_candidates(self) -> tuple[list[Any], dict[Any, list[Any]]]:
        if not self._is_goretrack_onslaught():
            return ([], {})
        if self.game is None:
            return ([], {})
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return ([], {})
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return ([], {})
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except ImportError:
            unit_wholly_within_range_of_unit = None
        mgr = self._get_world_eaters_mgr()
        candidates: List[Any] = []
        transports_by_unit: dict[Any, list[Any]] = {}
        seen: set[str] = set()
        enemy_units_getter = getattr(game_map, "get_enemy_units", None)
        engagement_checker = getattr(game_map, "is_within_engagement_range", None)
        for unit in list(getattr(army, "units", []) or []):
            root = self._goretrack_root(unit)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._is_unit_alive(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            if self._is_unit_in_reserves(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            has_keyword = getattr(root, "has_keyword", None)
            if not callable(has_keyword):
                continue
            try:
                if not has_keyword("INFANTRY"):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            engaged = False
            if callable(enemy_units_getter) and callable(engagement_checker):
                enemy_units = list(enemy_units_getter(root) or [])
                for enemy in enemy_units:
                    enemy_alive = getattr(enemy, "is_alive", None)
                    if callable(enemy_alive):
                        try:
                            if not bool(enemy_alive()):
                                continue
                        except (AttributeError, TypeError, ValueError):
                            continue
                    elif getattr(enemy, "is_alive", True) is False:
                        continue
                    if not bool(getattr(enemy, "deployed", True)):
                        continue
                    try:
                        if engagement_checker(root, enemy):
                            engaged = True
                            break
                    except (AttributeError, TypeError, ValueError):
                        continue
            if engaged:
                continue
            transports: list[Any] = []
            for transport in list(getattr(army, "units", []) or []):
                root_transport = self._goretrack_root(transport)
                if root_transport is None:
                    continue
                if not self._is_unit_alive(root_transport):
                    continue
                if not bool(getattr(root_transport, "deployed", False)):
                    continue
                if not bool(getattr(root_transport, "is_transport", False)):
                    continue
                can_transport = getattr(root_transport, "can_transport", None)
                if not callable(can_transport):
                    continue
                try:
                    if not can_transport(root):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
                if callable(unit_wholly_within_range_of_unit):
                    try:
                        if not unit_wholly_within_range_of_unit(
                            root_transport,
                            root,
                            6.0,
                            use_attached_aggregate=True,
                        ):
                            continue
                    except (AttributeError, TypeError, ValueError):
                        continue
                transports.append(root_transport)
            if not transports:
                continue
            transports_by_unit[root] = sorted(transports, key=self._goretrack_sort_key)
            candidates.append(root)
        return (sorted(candidates, key=self._goretrack_sort_key), transports_by_unit)

    def _goretrack_phase_key(self) -> str:
        game = getattr(self, "game", None)
        turn_raw = getattr(game, "turn", 0) if game is not None else 0
        try:
            battle_round = int(turn_raw or 0)
        except (TypeError, ValueError):
            battle_round = 0
        phase_name = ""
        phase = getattr(game, "phase", None) if game is not None else None
        if phase is not None:
            phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
        if not phase_name:
            phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().upper()
        get_current_player = getattr(game, "get_current_player", None) if game is not None else None
        current_player = get_current_player() if callable(get_current_player) else None
        owner = str(getattr(current_player, "id", "") or "")
        return f"{battle_round}:{phase_name}:{owner}"

    @staticmethod
    def _goretrack_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    def _goretrack_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _goretrack_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._goretrack_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _goretrack_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _use_world_eaters_goretrack_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "AGGRESSIVE DISEMBARKATION":
            return self._use_goretrack_aggressive_disembarkation(stratagem, **kwargs)
        if name_u == "FULL-THROTTLE ASSAULT":
            return self._use_goretrack_full_throttle_assault(stratagem, **kwargs)
        if name_u == "SMASH THROUGH":
            return self._use_goretrack_smash_through(stratagem, **kwargs)
        if name_u == "ENDLESS PURSUIT OF VIOLENCE":
            return self._use_goretrack_endless_pursuit_of_violence(stratagem, **kwargs)
        if name_u == "FURY UNLEASHED":
            return self._use_goretrack_fury_unleashed(stratagem, **kwargs)
        if name_u == "UNRELENTING ADVANCE":
            return self._use_goretrack_unrelenting_advance(stratagem, **kwargs)
        return None

    def _use_goretrack_aggressive_disembarkation(self, stratagem: Any, **kwargs) -> bool:
        transport_unit = (
            kwargs.get("unit")
            or kwargs.get("target_unit")
            or kwargs.get("transport_unit")
            or kwargs.get("transport")
        )
        embarked_unit = (
            kwargs.get("embarked_unit")
            or kwargs.get("passenger_unit")
            or kwargs.get("selected_embarked_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        if transport_unit is None and len(candidates) == 1:
            transport_unit = candidates[0]
        if transport_unit is None:
            print("ERROR: Aggressive Disembarkation: no transport provided")
            return False

        root = self._goretrack_root(transport_unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "movement phase":
            print("ERROR: Aggressive Disembarkation: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            print("ERROR: Aggressive Disembarkation: not your turn")
            return False
        if candidates and root not in candidates:
            print("ERROR: Aggressive Disembarkation: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: Aggressive Disembarkation: transport is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: Aggressive Disembarkation: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("RHINO")):
            print("ERROR: Aggressive Disembarkation: target is not a RHINO")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            print("ERROR: Aggressive Disembarkation: transport already moved this phase")
            return False

        valid_rhinos = self._goretrack_rhino_candidates(require_not_moved=True, require_any_passengers=True)
        if root not in valid_rhinos:
            print("ERROR: Aggressive Disembarkation: transport is not eligible")
            return False

        passengers = self._goretrack_embarked_units(
            root,
            require_world_eaters=True,
            require_khorne_berzerkers=False,
        )
        if not passengers:
            print("ERROR: Aggressive Disembarkation: no embarked units")
            return False
        if embarked_unit is None:
            if len(passengers) == 1:
                embarked_unit = passengers[0]
            else:
                print("ERROR: Aggressive Disembarkation: no embarked unit selected")
                return False
        if embarked_unit not in passengers:
            print("ERROR: Aggressive Disembarkation: embarked unit is not eligible")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False

        special_rules = getattr(embarked_unit, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["goretrack_aggressive_disembark_active"] = True
        special_rules["goretrack_aggressive_disembark_distance"] = 6.0
        special_rules["goretrack_aggressive_disembark_allow_engagement"] = True
        special_rules["goretrack_aggressive_disembark_transport_id"] = get_entity_id(root)
        special_rules["goretrack_aggressive_disembark_source"] = stratagem.name
        embarked_unit.special_rules = special_rules

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            raise RuntimeError("Aggressive Disembarkation requires an active game map.")
        try:
            ok = bool(
                embarked_unit.disembark(
                    game_map=game_map,
                    transport_unit=root,
                    current_turn=int(getattr(self.game, "turn", 0) or 0),
                )
            )
        finally:
            special_rules = getattr(embarked_unit, "special_rules", None)
            if isinstance(special_rules, dict):
                for key in (
                    "goretrack_aggressive_disembark_active",
                    "goretrack_aggressive_disembark_distance",
                    "goretrack_aggressive_disembark_allow_engagement",
                    "goretrack_aggressive_disembark_transport_id",
                    "goretrack_aggressive_disembark_source",
                ):
                    special_rules.pop(key, None)
                embarked_unit.special_rules = special_rules
        if not ok:
            print("ERROR: Aggressive Disembarkation: disembark failed")
            return False

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: AGGRESSIVE DISEMBARKATION: {getattr(embarked_unit, 'name', 'Unit')} disembarks within 6\".")
        return True

    def _use_goretrack_full_throttle_assault(self, stratagem: Any, **kwargs) -> bool:
        transport_unit = (
            kwargs.get("unit")
            or kwargs.get("target_unit")
            or kwargs.get("transport_unit")
            or kwargs.get("transport")
        )
        candidates = list(kwargs.get("candidates") or [])
        if transport_unit is None and len(candidates) == 1:
            transport_unit = candidates[0]
        if transport_unit is None:
            print("ERROR: Full-Throttle Assault: no transport provided")
            return False

        root = self._goretrack_root(transport_unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "movement phase":
            print("ERROR: Full-Throttle Assault: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            print("ERROR: Full-Throttle Assault: not your turn")
            return False
        if candidates and root not in candidates:
            print("ERROR: Full-Throttle Assault: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: Full-Throttle Assault: transport is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: Full-Throttle Assault: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("RHINO")):
            print("ERROR: Full-Throttle Assault: target is not a RHINO")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            print("ERROR: Full-Throttle Assault: transport already moved this phase")
            return False

        valid_rhinos = self._goretrack_rhino_candidates(require_not_moved=True, require_any_passengers=False)
        if root not in valid_rhinos:
            print("ERROR: Full-Throttle Assault: transport is not eligible")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False

        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["goretrack_full_throttle_assault_active"] = True
        special_rules["goretrack_full_throttle_assault_expires_phase"] = "MOVEMENT_PHASE"
        special_rules["goretrack_full_throttle_assault_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["goretrack_full_throttle_assault_turn"] = (
            int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        )
        special_rules["goretrack_full_throttle_assault_source"] = stratagem.name
        root.special_rules = special_rules

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: FULL-THROTTLE ASSAULT: {getattr(root, 'name', 'Unit')} disembarking units can charge after moving.")
        return True

    def _use_goretrack_smash_through(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            print("ERROR: Smash Through: no target unit provided")
            return False

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "movement phase":
            print("ERROR: Smash Through: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            print("ERROR: Smash Through: not your turn")
            return False
        if candidates and root not in candidates:
            print("ERROR: Smash Through: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: Smash Through: target unit is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: Smash Through: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        is_vehicle = bool(getattr(root, "is_vehicle", False))
        if callable(has_keyword):
            is_vehicle = is_vehicle or bool(has_keyword("VEHICLE"))
        if not is_vehicle:
            print("ERROR: Smash Through: target is not a VEHICLE")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            print("ERROR: Smash Through: target already moved this phase")
            return False

        valid_vehicles = self._goretrack_vehicle_candidates(require_not_moved=True)
        if root not in valid_vehicles:
            print("ERROR: Smash Through: target is not eligible")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False

        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        move_types = {"move", "advance"}
        current = set(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
        added = set()
        for move_type in move_types:
            if move_type not in current:
                current.add(move_type)
                added.add(move_type)
        if current:
            special_rules["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
        if added:
            special_rules["goretrack_smash_through_added_phase_move_terrain_only_types"] = sorted(added)
        special_rules["goretrack_smash_through_active"] = True
        special_rules["goretrack_smash_through_expires_phase"] = "MOVEMENT_PHASE"
        special_rules["goretrack_smash_through_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["goretrack_smash_through_turn"] = (
            int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        )
        special_rules["goretrack_smash_through_source"] = stratagem.name
        root.special_rules = special_rules

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: SMASH THROUGH: {getattr(root, 'name', 'Unit')} can move through terrain this phase.")
        return True

    def _use_goretrack_endless_pursuit_of_violence(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        transport_unit = kwargs.get("transport_unit") or kwargs.get("transport")
        if unit is None:
            for reaction in reversed(self._pending_reactions):
                if reaction.get("stratagem", "").strip().upper() != "ENDLESS PURSUIT OF VIOLENCE":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if transport_unit is None:
                    transport_unit = reaction.get("transport_unit") or reaction.get("transport")
                break
        if unit is None:
            print("WARN: Endless Pursuit of Violence: no target unit provided")
            return False

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "fight phase":
            print("WARN: Endless Pursuit of Violence: wrong phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("WARN: Endless Pursuit of Violence: target cannot be selected")
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("INFANTRY")):
            print("WARN: Endless Pursuit of Violence: target is not INFANTRY")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            print("WARN: Endless Pursuit of Violence: no map context")
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if callable(get_enemy_units) and callable(is_within_engagement_range):
            for enemy in list(get_enemy_units(root) or []):
                enemy_is_alive = getattr(enemy, "is_alive", None)
                if callable(enemy_is_alive) and not bool(enemy_is_alive()):
                    continue
                if not bool(getattr(enemy, "deployed", True)):
                    continue
                if is_within_engagement_range(root, enemy):
                    return False

        if transport_unit is None:
            mapping = kwargs.get("transport_candidates_by_unit") or {}
            transport_unit = (mapping.get(root) or [None])[0] if hasattr(mapping, "get") else None
        if transport_unit is None:
            _, transports_by_unit = self._goretrack_endless_pursuit_candidates()
            transport_unit = (transports_by_unit.get(root) or [None])[0]
        if transport_unit is None:
            print("WARN: Endless Pursuit of Violence: no transport provided")
            return False
        if not self._is_unit_alive(transport_unit):
            return False
        if not bool(getattr(transport_unit, "deployed", False)):
            return False
        can_transport = getattr(transport_unit, "can_transport", None)
        if not callable(can_transport) or not bool(can_transport(root)):
            return False

        from ..utility.aura_utils import unit_wholly_within_range_of_unit

        if not unit_wholly_within_range_of_unit(
            transport_unit,
            root,
            6.0,
            use_attached_aggregate=True,
        ):
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        if not bool(transport_unit.add_passenger(root, game_map=game_map)):
            print("WARN: Endless Pursuit of Violence: embark failed")
            return False

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(
            "INFO: Endless Pursuit of Violence: "
            f"{getattr(root, 'name', 'Unit')} embarked within {getattr(transport_unit, 'name', 'Transport')}."
        )
        return True

    def _use_goretrack_fury_unleashed(self, stratagem: Any, **kwargs) -> bool:
        transport_unit = (
            kwargs.get("unit")
            or kwargs.get("target_unit")
            or kwargs.get("transport_unit")
            or kwargs.get("transport")
        )
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
        embarked_unit = (
            kwargs.get("embarked_unit")
            or kwargs.get("passenger_unit")
            or kwargs.get("selected_embarked_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        if transport_unit is None:
            if len(candidates) == 1:
                transport_unit = candidates[0]
            if transport_unit is None:
                for reaction in reversed(self._pending_reactions):
                    if reaction.get("stratagem", "").strip().upper() != "FURY UNLEASHED":
                        continue
                    transport_unit = reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit")
                    candidates = candidates or list(reaction.get("candidates") or [])
                    if transport_unit is None and len(candidates) == 1:
                        transport_unit = candidates[0]
                    break
        if transport_unit is None:
            print("ERROR: Fury Unleashed: no transport provided")
            return False

        root = self._goretrack_root(transport_unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "shooting phase":
            print("ERROR: Fury Unleashed: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            print("ERROR: Fury Unleashed: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            print("ERROR: Fury Unleashed: target was not selected by the attacker")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: Fury Unleashed: transport is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: Fury Unleashed: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("RHINO")):
            print("ERROR: Fury Unleashed: target is not a RHINO")
            return False

        special_rules = getattr(root, "special_rules", None)
        if isinstance(special_rules, dict):
            phase_key = self._goretrack_phase_key()
            if str(special_rules.get("goretrack_unrelenting_advance_phase_key", "") or "") == phase_key:
                print("ERROR: Fury Unleashed: unit already targeted by Unrelenting Advance this phase")
                return False

        passengers = self._goretrack_embarked_units(
            root,
            require_world_eaters=True,
            require_khorne_berzerkers=True,
        )
        if not passengers:
            print("ERROR: Fury Unleashed: no embarked KHORNE BERZERKERS unit")
            return False
        if embarked_unit is None:
            if len(passengers) == 1:
                embarked_unit = passengers[0]
            else:
                print("ERROR: Fury Unleashed: no embarked unit selected")
                return False
        if embarked_unit not in passengers:
            print("ERROR: Fury Unleashed: embarked unit is not eligible")
            return False
        if enemy_unit is not None and self._goretrack_owned_by_player(enemy_unit, self.player):
            print("ERROR: Fury Unleashed: attacker is not enemy")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            raise RuntimeError("Fury Unleashed requires an active game map.")
        ok = bool(
            embarked_unit.disembark(
                game_map=game_map,
                transport_unit=root,
                current_turn=int(getattr(self.game, "turn", 0) or 0),
            )
        )
        if not ok:
            print("ERROR: Fury Unleashed: disembark failed")
            return False

        can_blood_surge = getattr(embarked_unit, "can_blood_surge", None)
        if callable(can_blood_surge) and bool(can_blood_surge(game=self.game, game_map=game_map)):
            roll_blood_surge_distance = getattr(self.game, "roll_blood_surge_distance", None)
            max_distance = int(roll_blood_surge_distance(embarked_unit) or 0) if callable(roll_blood_surge_distance) else 0
            if max_distance > 0:
                queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None)
                if callable(queue_move):
                    queue_move(
                        player=self.player,
                        unit=embarked_unit,
                        max_distance=int(max_distance),
                        kind="blood_surge",
                        movement_type="blood_surge",
                        source=stratagem.name,
                        attacker_unit=enemy_unit,
                    )

        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["goretrack_fury_unleashed_phase_key"] = self._goretrack_phase_key()
        root.special_rules = special_rules

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: FURY UNLEASHED: {getattr(embarked_unit, 'name', 'Unit')} disembarks and Blood Surges.")
        return True

    def _use_goretrack_unrelenting_advance(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            if unit is None:
                for reaction in reversed(self._pending_reactions):
                    if reaction.get("stratagem", "").strip().upper() != "UNRELENTING ADVANCE":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit")
                    candidates = candidates or list(reaction.get("candidates") or [])
                    if unit is None and len(candidates) == 1:
                        unit = candidates[0]
                    break
        if unit is None:
            print("ERROR: UNRELENTING ADVANCE: no target unit provided")
            return False

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "shooting phase":
            print("ERROR: UNRELENTING ADVANCE: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            print("ERROR: UNRELENTING ADVANCE: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            print("ERROR: UNRELENTING ADVANCE: target was not selected by the attacker")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: UNRELENTING ADVANCE: target unit is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: UNRELENTING ADVANCE: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        is_vehicle = bool(getattr(root, "is_vehicle", False))
        if callable(has_keyword):
            is_vehicle = is_vehicle or bool(has_keyword("VEHICLE"))
        if not is_vehicle:
            print("ERROR: UNRELENTING ADVANCE: target is not a VEHICLE")
            return False

        special_rules = getattr(root, "special_rules", None)
        if isinstance(special_rules, dict):
            phase_key = self._goretrack_phase_key()
            if str(special_rules.get("goretrack_fury_unleashed_phase_key", "") or "") == phase_key:
                print("ERROR: UNRELENTING ADVANCE: unit already targeted by Fury Unleashed this phase")
                return False
        if enemy_unit is not None and self._goretrack_owned_by_player(enemy_unit, self.player):
            print("ERROR: UNRELENTING ADVANCE: attacker is not enemy")
            return False

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            print("ERROR: UNRELENTING ADVANCE: no map context")
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if callable(get_enemy_units) and callable(is_within_engagement_range):
            for enemy in list(get_enemy_units(root) or []):
                enemy_is_alive = getattr(enemy, "is_alive", None)
                if callable(enemy_is_alive) and not bool(enemy_is_alive()):
                    continue
                if not bool(getattr(enemy, "deployed", True)):
                    continue
                if is_within_engagement_range(root, enemy):
                    print("ERROR: UNRELENTING ADVANCE: unit is in Engagement Range")
                    return False

        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=root,
                max_distance=6,
                kind="unrelenting_advance",
                movement_type="reactive",
                source=stratagem.name,
                attacker_unit=enemy_unit,
            )

        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["goretrack_unrelenting_advance_phase_key"] = self._goretrack_phase_key()
        root.special_rules = special_rules

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: UNRELENTING ADVANCE: {getattr(root, 'name', 'Unit')} can move up to 6\".")
        return True
