from __future__ import annotations

from typing import Any, List

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
