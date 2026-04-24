from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..engine.decision_port import get_decision_provider
from ..utility.entity_ids import get_entity_id
import logging
logger = logging.getLogger(__name__)


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

    def _is_khorne_daemonkin_detachment(self) -> bool:
        mgr = self._get_world_eaters_mgr()
        checker = getattr(mgr, "is_khorne_daemonkin", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_blood_legions_unit(self, unit: Any, mgr=None) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if mgr is None:
            mgr = self._get_world_eaters_mgr()
        unit_is_blood_legions = getattr(mgr, "unit_is_blood_legions", None) if mgr is not None else None
        if callable(unit_is_blood_legions):
            return bool(unit_is_blood_legions(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword("BLOOD LEGIONS"))
        return False

    def _we_friendly_battlefield_units(self) -> List[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
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
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _we_distance_between_units(self, first: Any, second: Any) -> Optional[float]:
        if self.game is None or first is None or second is None:
            return None
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return None
        distance_fn = getattr(game_map, "get_distance_between_units", None)
        if not callable(distance_fn):
            return None
        try:
            distance = distance_fn(first, second)
        except (AttributeError, TypeError, ValueError):
            return None
        if distance is None:
            return None
        return float(distance)

    @staticmethod
    def _we_has_returnable_blood_legions_model(unit: Any) -> bool:
        root = unit
        if root is None:
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword):
            return False
        try:
            if not (has_keyword("MOUNTED") or has_keyword("BEAST") or has_keyword("INFANTRY")):
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        return bool(list(getattr(root, "models_lost", []) or []))

    def _we_khorne_daemonkin_daemonic_fury_supports(self, blood_legions_unit: Any) -> List[Any]:
        target_root = self._goretrack_root(blood_legions_unit)
        if target_root is None:
            return []
        mgr = self._get_world_eaters_mgr()
        supports: List[Any] = []
        for candidate in self._we_friendly_battlefield_units():
            root = self._goretrack_root(candidate)
            if root is None or root is target_root:
                continue
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            distance = self._we_distance_between_units(target_root, root)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            supports.append(root)
        return sorted(supports, key=self._goretrack_sort_key)

    def _we_khorne_daemonkin_daemontide_supports(self, world_eaters_unit: Any) -> List[Any]:
        target_root = self._goretrack_root(world_eaters_unit)
        if target_root is None:
            return []
        mgr = self._get_world_eaters_mgr()
        supports: List[Any] = []
        for candidate in self._we_friendly_battlefield_units():
            root = self._goretrack_root(candidate)
            if root is None or root is target_root:
                continue
            if not self._is_blood_legions_unit(root, mgr=mgr):
                continue
            if not self._we_has_returnable_blood_legions_model(root):
                continue
            distance = self._we_distance_between_units(target_root, root)
            if distance is None or distance > 6.0 + 1e-6:
                continue
            supports.append(root)
        return sorted(supports, key=self._goretrack_sort_key)

    def _we_khorne_daemonkin_tool_action_context(self, stratagem_name: str) -> Dict[str, Any]:
        name_u = str(stratagem_name or "").strip().upper()
        if not self._is_khorne_daemonkin_detachment():
            return {}
        mgr = self._get_world_eaters_mgr()
        candidates: List[Any] = []
        support_by_unit: Dict[str, List[Any]] = {}
        for unit in self._we_friendly_battlefield_units():
            root = self._goretrack_root(unit)
            if root is None:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if name_u == "DAEMONIC FURY":
                if not self._is_blood_legions_unit(root, mgr=mgr):
                    continue
                supports = self._we_khorne_daemonkin_daemonic_fury_supports(root)
            elif name_u == "DAEMONTIDE":
                if not self._is_world_eaters_unit(root, mgr=mgr):
                    continue
                supports = self._we_khorne_daemonkin_daemontide_supports(root)
            else:
                return {}
            if not supports:
                continue
            candidates.append(root)
            uid = self._goretrack_sort_key(root)
            if uid:
                support_by_unit[uid] = list(supports)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return {}
        return {
            "candidates": candidates,
            "support_candidates_by_unit": support_by_unit,
        }

    def _we_can_use_khorne_daemonkin_tool_action(self, stratagem_name: str, kwargs: Dict[str, Any]) -> bool:
        name_u = str(stratagem_name or "").strip().upper()
        if name_u not in {"DAEMONIC FURY", "DAEMONTIDE"}:
            return False
        if not self._is_khorne_daemonkin_detachment():
            return False
        phase_name = str((kwargs or {}).get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if name_u == "DAEMONIC FURY" and phase_name != "fight phase":
            return False
        if name_u == "DAEMONTIDE" and phase_name != "command phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False

        context = dict(kwargs or {})
        target_unit = context.get("target_unit") or context.get("unit")
        support_unit = context.get("support_unit")
        if name_u == "DAEMONIC FURY":
            target_unit = target_unit or context.get("blood_legions_unit")
            support_unit = support_unit or context.get("world_eaters_unit") or context.get("we_unit")
        else:
            target_unit = target_unit or context.get("world_eaters_unit")
            support_unit = support_unit or context.get("blood_legions_unit") or context.get("bl_unit")

        if target_unit is None:
            candidate_context = self._we_khorne_daemonkin_tool_action_context(name_u)
            return bool(candidate_context.get("candidates"))

        target_root = self._goretrack_root(target_unit)
        if target_root is None or self._unit_cannot_be_target_of_stratagem(target_root):
            return False
        mgr = self._get_world_eaters_mgr()
        if name_u == "DAEMONIC FURY":
            if not self._is_blood_legions_unit(target_root, mgr=mgr):
                return False
            supports = self._we_khorne_daemonkin_daemonic_fury_supports(target_root)
        else:
            if not self._is_world_eaters_unit(target_root, mgr=mgr):
                return False
            supports = self._we_khorne_daemonkin_daemontide_supports(target_root)
        if not supports:
            return False
        if support_unit is None:
            return True
        support_root = self._goretrack_root(support_unit)
        if support_root is None:
            return False
        support_id = self._goretrack_sort_key(support_root)
        return any(self._goretrack_sort_key(candidate) == support_id for candidate in supports)

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
            logger.error("ERROR: Aggressive Disembarkation: no transport provided")
            return False

        root = self._goretrack_root(transport_unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "movement phase":
            logger.error("ERROR: Aggressive Disembarkation: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            logger.error("ERROR: Aggressive Disembarkation: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: Aggressive Disembarkation: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: Aggressive Disembarkation: transport is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: Aggressive Disembarkation: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("RHINO")):
            logger.error("ERROR: Aggressive Disembarkation: target is not a RHINO")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: Aggressive Disembarkation: transport already moved this phase")
            return False

        valid_rhinos = self._goretrack_rhino_candidates(require_not_moved=True, require_any_passengers=True)
        if root not in valid_rhinos:
            logger.error("ERROR: Aggressive Disembarkation: transport is not eligible")
            return False

        passengers = self._goretrack_embarked_units(
            root,
            require_world_eaters=True,
            require_khorne_berzerkers=False,
        )
        if not passengers:
            logger.error("ERROR: Aggressive Disembarkation: no embarked units")
            return False
        if embarked_unit is None:
            if len(passengers) == 1:
                embarked_unit = passengers[0]
            else:
                logger.error("ERROR: Aggressive Disembarkation: no embarked unit selected")
                return False
        if embarked_unit not in passengers:
            logger.error("ERROR: Aggressive Disembarkation: embarked unit is not eligible")
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
            logger.error("ERROR: Aggressive Disembarkation: disembark failed")
            return False

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: AGGRESSIVE DISEMBARKATION: {getattr(embarked_unit, 'name', 'Unit')} disembarks within 6\".")
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
            logger.error("ERROR: Full-Throttle Assault: no transport provided")
            return False

        root = self._goretrack_root(transport_unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "movement phase":
            logger.error("ERROR: Full-Throttle Assault: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            logger.error("ERROR: Full-Throttle Assault: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: Full-Throttle Assault: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: Full-Throttle Assault: transport is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: Full-Throttle Assault: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("RHINO")):
            logger.error("ERROR: Full-Throttle Assault: target is not a RHINO")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: Full-Throttle Assault: transport already moved this phase")
            return False

        valid_rhinos = self._goretrack_rhino_candidates(require_not_moved=True, require_any_passengers=False)
        if root not in valid_rhinos:
            logger.error("ERROR: Full-Throttle Assault: transport is not eligible")
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
        logger.info(f"INFO: FULL-THROTTLE ASSAULT: {getattr(root, 'name', 'Unit')} disembarking units can charge after moving.")
        return True

    def _use_goretrack_smash_through(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: Smash Through: no target unit provided")
            return False

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "movement phase":
            logger.error("ERROR: Smash Through: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            logger.error("ERROR: Smash Through: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: Smash Through: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: Smash Through: target unit is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: Smash Through: target cannot be selected")
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
            logger.error("ERROR: Smash Through: target is not a VEHICLE")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: Smash Through: target already moved this phase")
            return False

        valid_vehicles = self._goretrack_vehicle_candidates(require_not_moved=True)
        if root not in valid_vehicles:
            logger.error("ERROR: Smash Through: target is not eligible")
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
        logger.info(f"INFO: SMASH THROUGH: {getattr(root, 'name', 'Unit')} can move through terrain this phase.")
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
            logger.warning("WARN: Endless Pursuit of Violence: no target unit provided")
            return False

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "fight phase":
            logger.warning("WARN: Endless Pursuit of Violence: wrong phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.warning("WARN: Endless Pursuit of Violence: target cannot be selected")
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("INFANTRY")):
            logger.warning("WARN: Endless Pursuit of Violence: target is not INFANTRY")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            logger.warning("WARN: Endless Pursuit of Violence: no map context")
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
            logger.warning("WARN: Endless Pursuit of Violence: no transport provided")
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
            logger.warning("WARN: Endless Pursuit of Violence: embark failed")
            return False

        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: Endless Pursuit of Violence: "
            f"{getattr(root, 'name', 'Unit')} embarked within {getattr(transport_unit, 'name', 'Transport')}.")
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
            logger.error("ERROR: Fury Unleashed: no transport provided")
            return False

        root = self._goretrack_root(transport_unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "shooting phase":
            logger.error("ERROR: Fury Unleashed: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: Fury Unleashed: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: Fury Unleashed: target was not selected by the attacker")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: Fury Unleashed: transport is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: Fury Unleashed: target cannot be selected")
            return False
        if not self._is_unit_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if not callable(has_keyword) or not bool(has_keyword("RHINO")):
            logger.error("ERROR: Fury Unleashed: target is not a RHINO")
            return False

        special_rules = getattr(root, "special_rules", None)
        if isinstance(special_rules, dict):
            phase_key = self._goretrack_phase_key()
            if str(special_rules.get("goretrack_unrelenting_advance_phase_key", "") or "") == phase_key:
                logger.error("ERROR: Fury Unleashed: unit already targeted by Unrelenting Advance this phase")
                return False

        passengers = self._goretrack_embarked_units(
            root,
            require_world_eaters=True,
            require_khorne_berzerkers=True,
        )
        if not passengers:
            logger.error("ERROR: Fury Unleashed: no embarked KHORNE BERZERKERS unit")
            return False
        if embarked_unit is None:
            if len(passengers) == 1:
                embarked_unit = passengers[0]
            else:
                logger.error("ERROR: Fury Unleashed: no embarked unit selected")
                return False
        if embarked_unit not in passengers:
            logger.error("ERROR: Fury Unleashed: embarked unit is not eligible")
            return False
        if enemy_unit is not None and self._goretrack_owned_by_player(enemy_unit, self.player):
            logger.error("ERROR: Fury Unleashed: attacker is not enemy")
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
            logger.error("ERROR: Fury Unleashed: disembark failed")
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
        logger.info(f"INFO: FURY UNLEASHED: {getattr(embarked_unit, 'name', 'Unit')} disembarks and Blood Surges.")
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
            logger.error("ERROR: UNRELENTING ADVANCE: no target unit provided")
            return False

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_goretrack_onslaught():
            return False
        phase_name = kwargs.get("phase_name") or self._current_phase_name or ""
        if str(phase_name).strip().lower() != "shooting phase":
            logger.error("ERROR: UNRELENTING ADVANCE: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: UNRELENTING ADVANCE: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: UNRELENTING ADVANCE: target was not selected by the attacker")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: UNRELENTING ADVANCE: target unit is not yours")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNRELENTING ADVANCE: target cannot be selected")
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
            logger.error("ERROR: UNRELENTING ADVANCE: target is not a VEHICLE")
            return False

        special_rules = getattr(root, "special_rules", None)
        if isinstance(special_rules, dict):
            phase_key = self._goretrack_phase_key()
            if str(special_rules.get("goretrack_fury_unleashed_phase_key", "") or "") == phase_key:
                logger.error("ERROR: UNRELENTING ADVANCE: unit already targeted by Fury Unleashed this phase")
                return False
        if enemy_unit is not None and self._goretrack_owned_by_player(enemy_unit, self.player):
            logger.error("ERROR: UNRELENTING ADVANCE: attacker is not enemy")
            return False

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            logger.error("ERROR: UNRELENTING ADVANCE: no map context")
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
                    logger.error("ERROR: UNRELENTING ADVANCE: unit is in Engagement Range")
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
        logger.info(f"INFO: UNRELENTING ADVANCE: {getattr(root, 'name', 'Unit')} can move up to 6\".")
        return True

    def _is_possessed_slaughterband(self) -> bool:
        mgr = self._get_world_eaters_mgr()
        checker = getattr(mgr, "is_possessed_slaughterband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _possessed_normalized_name(unit: Any) -> str:
        text = str(getattr(unit, "name", "") or "").strip().lower()
        return " ".join(text.replace("-", " ").split())

    def _is_exalted_eightbound_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        name = self._possessed_normalized_name(root)
        if "exalted eightbound" in name:
            return True
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                if bool(has_any_keyword("EXALTED EIGHTBOUND")):
                    return True
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def _is_eightbound_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._is_exalted_eightbound_unit(root):
            return True
        name = self._possessed_normalized_name(root)
        if "eightbound" in name:
            return True
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                if bool(has_any_keyword("EIGHTBOUND")):
                    return True
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def _is_world_eaters_possessed_unit(self, unit: Any, *, mgr=None) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if mgr is None:
            mgr = self._get_world_eaters_mgr()
        if not self._is_world_eaters_unit(root, mgr=mgr):
            return False
        has_keyword = getattr(root, "has_keyword", None)
        if callable(has_keyword):
            try:
                if bool(has_keyword("POSSESSED")):
                    return True
            except (AttributeError, TypeError, ValueError):
                return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword("POSSESSED"))
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def _possessed_slaughterband_candidates(
        self,
        *,
        require_on_battlefield: bool = True,
        require_not_fought: bool = False,
        require_not_moved: bool = False,
        require_not_attempted_charge: bool = False,
        require_in_reserves: bool = False,
        require_deep_strike: bool = False,
        require_exalted_eightbound: bool = False,
    ) -> list[Any]:
        if not self._is_possessed_slaughterband():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_world_eaters_mgr()
        candidates: list[Any] = []
        seen: set[str] = set()
        fight_mgr = getattr(self.game, "fight_phase_manager", None) if self.game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or [])
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
            if not self._is_world_eaters_possessed_unit(root, mgr=mgr):
                continue
            if require_exalted_eightbound and not self._is_exalted_eightbound_unit(root):
                continue
            on_battlefield = bool(getattr(root, "deployed", False)) and not self._is_unit_in_reserves(root)
            if on_battlefield and (bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None))):
                on_battlefield = False
            if require_on_battlefield and not on_battlefield:
                continue
            if require_in_reserves and not self._is_unit_in_reserves(root):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            if require_not_fought:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "fought_this_phase", False)):
                    continue
                if root in fought_units:
                    continue
            if require_not_moved:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "moved_this_round", False)):
                    continue
            if require_not_attempted_charge:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "attempted_charge_this_round", False)):
                    continue
            if require_deep_strike:
                has_deep_strike = getattr(root, "has_deep_strike", None)
                if not callable(has_deep_strike):
                    continue
                try:
                    if not bool(has_deep_strike()):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _possessed_unit_has_engaged_enemy(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._goretrack_root(enemy)
            if enemy_root is None:
                continue
            if not self._is_unit_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            try:
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _possessed_candidate_selected(self, unit: Any, candidates: list[Any]) -> bool:
        candidate_ids = self._candidate_ids(candidates)
        if not candidate_ids:
            return True
        return self._goretrack_sort_key(unit) in candidate_ids

    def _we_possessed_tool_action_candidates(self, stratagem_name: str, *, phase_name: str = "") -> list[Any]:
        name_u = str(stratagem_name or "").strip().upper()
        phase_name_l = str(phase_name or self._current_phase_name or "").strip().lower()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if name_u == "DAEMONIC STRENGTH":
            if phase_name_l != "fight phase":
                return []
            return self._possessed_slaughterband_candidates(
                require_on_battlefield=True,
                require_not_fought=True,
            )
        if name_u == "IMMORTAL FURY":
            if phase_name_l != "fight phase":
                return []
            return self._possessed_slaughterband_candidates(
                require_on_battlefield=True,
                require_not_fought=True,
            )
        if name_u == "HORRIFYING VIOLENCE":
            if phase_name_l != "command phase" or active_player is self.player:
                return []
            return [
                unit
                for unit in self._possessed_slaughterband_candidates(require_on_battlefield=True)
                if self._possessed_unit_has_engaged_enemy(unit)
            ]
        if name_u == "RAPID MANIFESTATION":
            if phase_name_l != "movement phase" or active_player is not self.player:
                return []
            turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            candidates: list[Any] = []
            for unit in self._possessed_slaughterband_candidates(
                require_on_battlefield=False,
                require_in_reserves=True,
                require_deep_strike=True,
                require_exalted_eightbound=True,
            ):
                can_arrive = getattr(unit, "can_arrive_from_reserves", None)
                if callable(can_arrive) and not bool(can_arrive(turn)):
                    continue
                candidates.append(unit)
            return candidates
        if name_u == "WARP STALKERS":
            if phase_name_l == "movement phase":
                if active_player is not self.player:
                    return []
                return self._possessed_slaughterband_candidates(
                    require_on_battlefield=True,
                    require_not_moved=True,
                )
            if phase_name_l == "charge phase":
                if active_player is not self.player:
                    return []
                return self._possessed_slaughterband_candidates(
                    require_on_battlefield=True,
                    require_not_attempted_charge=True,
                )
            return []
        return []

    def _we_possessed_tool_action_context(self, stratagem_name: str, *, phase_name: str = "") -> Dict[str, Any]:
        candidates = self._we_possessed_tool_action_candidates(stratagem_name, phase_name=phase_name)
        if not candidates:
            return {}
        return {"candidates": list(candidates)}

    def _we_can_use_possessed_tool_action(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Optional[bool]:
        name_u = str(stratagem_name or "").strip().upper()
        if name_u not in {
            "DAEMONIC STRENGTH",
            "IMMORTAL FURY",
            "HORRIFYING VIOLENCE",
            "RAPID MANIFESTATION",
            "WARP STALKERS",
        }:
            return None
        if not self._is_possessed_slaughterband():
            return False

        unit, candidates, attacking_unit = self._possessed_target_from_kwargs(name_u, kwargs)
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        allowed_candidates = list(candidates or [])
        if not allowed_candidates:
            allowed_candidates = self._we_possessed_tool_action_candidates(name_u, phase_name=phase_name)
        if unit is None:
            return bool(allowed_candidates)

        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not allowed_candidates:
            return False
        if not self._possessed_candidate_selected(root, candidates):
            return False
        if allowed_candidates:
            allowed_ids = self._candidate_ids(allowed_candidates)
            if self._goretrack_sort_key(root) not in allowed_ids:
                return False
        if not self._goretrack_owned_by_player(root, self.player):
            return False
        if name_u == "IMMORTAL FURY" and attacking_unit is not None and self._goretrack_owned_by_player(attacking_unit, self.player):
            return False
        return True

    def _possessed_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        attacking_unit: Any = None,
    ) -> bool:
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if attacking_unit is not None and reaction.get("attacking_unit") is not attacking_unit:
                continue
            return True
        return False

    def _queue_world_eaters_possessed_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_possessed_slaughterband():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "COMMAND_PHASE":
            return
        if player is self.player:
            return
        stratagem = self.get_by_name("HORRIFYING VIOLENCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return
        candidates: list[Any] = []
        for root in self._possessed_slaughterband_candidates(require_on_battlefield=True):
            engaged = False
            for enemy in list(game_map.get_enemy_units(root) or []):
                try:
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
                if not bool(getattr(enemy, "deployed", True)):
                    continue
                try:
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                except (AttributeError, TypeError, ValueError):
                    continue
            if engaged:
                candidates.append(root)
        if not candidates:
            return
        if self._possessed_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Command phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": "Command phase",
            "phase_name": "Command phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_world_eaters_possessed_fight_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_possessed_slaughterband():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        try:
            if attacking_unit.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        stratagem = self.get_by_name("IMMORTAL FURY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        possible = set(self._possessed_slaughterband_candidates(require_on_battlefield=True, require_not_fought=True))
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._goretrack_root(unit)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root in possible:
                candidates.append(root)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return
        if self._possessed_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            attacking_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _possessed_target_from_kwargs(self, stratagem_name: str, kwargs: dict[str, Any]) -> tuple[Any, list[Any], Any]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("attacker_unit") or reaction.get("enemy_unit")
                break
        return unit, candidates, attacking_unit

    def _candidate_ids(self, candidates: list[Any]) -> set[str]:
        ids: set[str] = set()
        for candidate in list(candidates or []):
            root = self._goretrack_root(candidate)
            uid = self._goretrack_sort_key(root)
            if uid:
                ids.add(uid)
        return ids

    def _use_world_eaters_possessed_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "DAEMONIC STRENGTH":
            return self._use_possessed_daemonic_strength(stratagem, **kwargs)
        if name_u == "IMMORTAL FURY":
            return self._use_possessed_immortal_fury(stratagem, **kwargs)
        if name_u == "RAPID MANIFESTATION":
            return self._use_possessed_rapid_manifestation(stratagem, **kwargs)
        if name_u == "HORRIFYING VIOLENCE":
            return self._use_possessed_horrifying_violence(stratagem, **kwargs)
        if name_u == "WARP STALKERS":
            return self._use_possessed_warp_stalkers(stratagem, **kwargs)
        return None

    def _use_possessed_daemonic_strength(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _attacking_unit = self._possessed_target_from_kwargs("DAEMONIC STRENGTH", kwargs)
        if unit is None:
            print("ERROR: DAEMONIC STRENGTH: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_possessed_slaughterband():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            print("ERROR: DAEMONIC STRENGTH: wrong phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            print("ERROR: DAEMONIC STRENGTH: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: DAEMONIC STRENGTH: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        if not self._is_world_eaters_possessed_unit(root):
            print("ERROR: DAEMONIC STRENGTH: target must be a WORLD EATERS POSSESSED unit")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            print("ERROR: DAEMONIC STRENGTH: target already fought this phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: DAEMONIC STRENGTH: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["possessed_daemonic_strength_active"] = True
        sr["possessed_daemonic_strength_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["possessed_daemonic_strength_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["possessed_daemonic_strength_expires_phase"] = "FIGHT_PHASE"
        sr["possessed_daemonic_strength_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: DAEMONIC STRENGTH: {getattr(root, 'name', 'Unit')} gains conditional +1 Damage this phase.")
        return True

    def _use_possessed_immortal_fury(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, attacking_unit = self._possessed_target_from_kwargs("IMMORTAL FURY", kwargs)
        if unit is None:
            print("ERROR: IMMORTAL FURY: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_possessed_slaughterband():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            print("ERROR: IMMORTAL FURY: wrong phase")
            return False
        if attacking_unit is not None and self._goretrack_owned_by_player(attacking_unit, self.player):
            print("ERROR: IMMORTAL FURY: attacker is not enemy")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            print("ERROR: IMMORTAL FURY: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: IMMORTAL FURY: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        if not self._is_world_eaters_possessed_unit(root):
            print("ERROR: IMMORTAL FURY: target must be a WORLD EATERS POSSESSED unit")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            print("ERROR: IMMORTAL FURY: target already fought this phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: IMMORTAL FURY: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["immortal_fury_active"] = True
        sr["immortal_fury_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["immortal_fury_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["immortal_fury_expires_phase"] = "FIGHT_PHASE"
        sr["immortal_fury_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: IMMORTAL FURY: {getattr(root, 'name', 'Unit')} can fight on death this phase.")
        return True

    def _use_possessed_rapid_manifestation(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _attacking_unit = self._possessed_target_from_kwargs("RAPID MANIFESTATION", kwargs)
        if unit is None:
            print("ERROR: RAPID MANIFESTATION: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_possessed_slaughterband():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            print("ERROR: RAPID MANIFESTATION: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            print("ERROR: RAPID MANIFESTATION: not your turn")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            print("ERROR: RAPID MANIFESTATION: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: RAPID MANIFESTATION: target unit is not yours")
            return False
        if not self._is_unit_alive(root):
            return False
        if not self._is_world_eaters_possessed_unit(root):
            print("ERROR: RAPID MANIFESTATION: target must be a WORLD EATERS POSSESSED unit")
            return False
        if not self._is_exalted_eightbound_unit(root):
            print("ERROR: RAPID MANIFESTATION: target must be EXALTED EIGHTBOUND")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: RAPID MANIFESTATION: target cannot be selected")
            return False
        if not self._is_unit_in_reserves(root):
            print("ERROR: RAPID MANIFESTATION: target must be in Reserves")
            return False
        has_deep_strike = getattr(root, "has_deep_strike", None)
        if not callable(has_deep_strike) or not bool(has_deep_strike()):
            print("ERROR: RAPID MANIFESTATION: target lacks Deep Strike")
            return False
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        can_arrive = getattr(root, "can_arrive_from_reserves", None)
        if callable(can_arrive) and not bool(can_arrive(turn)):
            print("ERROR: RAPID MANIFESTATION: target cannot arrive from Reserves this turn")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["rapid_manifestation_deep_strike_min_distance"] = 6.0
        sr["rapid_manifestation_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rapid_manifestation_turn"] = turn
        sr["rapid_manifestation_expires_phase"] = "MOVEMENT_PHASE"
        sr["rapid_manifestation_source"] = stratagem.name
        sr["rapid_manifestation_no_charge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rapid_manifestation_no_charge_turn"] = turn
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: RAPID MANIFESTATION: {getattr(root, 'name', 'Unit')} can Deep Strike within 6\" and cannot charge this turn.")
        return True

    def _use_possessed_horrifying_violence(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _attacking_unit = self._possessed_target_from_kwargs("HORRIFYING VIOLENCE", kwargs)
        if unit is None:
            print("ERROR: HORRIFYING VIOLENCE: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_possessed_slaughterband():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            print("ERROR: HORRIFYING VIOLENCE: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            print("ERROR: HORRIFYING VIOLENCE: not opponent's Command phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            print("ERROR: HORRIFYING VIOLENCE: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: HORRIFYING VIOLENCE: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        if not self._is_world_eaters_possessed_unit(root):
            print("ERROR: HORRIFYING VIOLENCE: target must be a WORLD EATERS POSSESSED unit")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: HORRIFYING VIOLENCE: target cannot be selected")
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        affected: list[Any] = []
        seen_enemy: set[str] = set()
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._goretrack_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._goretrack_sort_key(enemy_root)
            if enemy_id and enemy_id in seen_enemy:
                continue
            if enemy_id:
                seen_enemy.add(enemy_id)
            if not self._is_unit_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            try:
                if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) - 1
            reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            reasons.append("Horrifying Violence")
            sr["battle_shock_test_modifier_reasons"] = reasons
            enemy_root.special_rules = sr
            take_test = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(turn)
            affected.append(enemy_root)
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: HORRIFYING VIOLENCE: {len(affected)} enemy unit(s) took Battle-shock tests at -1.")
        return True

    def _use_possessed_warp_stalkers(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _attacking_unit = self._possessed_target_from_kwargs("WARP STALKERS", kwargs)
        if unit is None:
            print("ERROR: WARP STALKERS: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_possessed_slaughterband():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            print("ERROR: WARP STALKERS: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            print("ERROR: WARP STALKERS: not your turn")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            print("ERROR: WARP STALKERS: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            print("ERROR: WARP STALKERS: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        if not self._is_world_eaters_possessed_unit(root):
            print("ERROR: WARP STALKERS: target must be a WORLD EATERS POSSESSED unit")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            print("ERROR: WARP STALKERS: target cannot be selected")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "movement phase" and bool(getattr(round_state, "moved_this_round", False)):
            print("ERROR: WARP STALKERS: target already moved this phase")
            return False
        if phase_name == "charge phase" and bool(getattr(round_state, "attempted_charge_this_round", False)):
            print("ERROR: WARP STALKERS: target already attempted a charge this phase")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        move_types = {"move", "advance", "fall_back", "charge"}
        engagement_types = {"move", "advance", "fall_back"}
        block_types = {"move", "advance", "fall_back", "charge"}

        current_move_types = set(sr.get("bearer_unit_phase_move_types") or [])
        added_move_types = sorted([t for t in sorted(move_types) if t not in current_move_types])
        if added_move_types:
            current_move_types.update(added_move_types)
            sr["bearer_unit_phase_move_types"] = sorted(current_move_types)
            sr["warp_stalkers_added_phase_move_types"] = added_move_types

        current_engagement_types = set(sr.get("bearer_unit_phase_move_engagement_types") or [])
        added_engagement_types = sorted([t for t in sorted(engagement_types) if t not in current_engagement_types])
        if added_engagement_types:
            current_engagement_types.update(added_engagement_types)
            sr["bearer_unit_phase_move_engagement_types"] = sorted(current_engagement_types)
            sr["warp_stalkers_added_phase_move_engagement_types"] = added_engagement_types

        current_block_types = set(sr.get("bearer_unit_phase_move_block_monster_vehicle_types") or [])
        added_block_types = sorted([t for t in sorted(block_types) if t not in current_block_types])
        if added_block_types:
            current_block_types.update(added_block_types)
            sr["bearer_unit_phase_move_block_monster_vehicle_types"] = sorted(current_block_types)
            sr["warp_stalkers_added_phase_move_block_monster_vehicle_types"] = added_block_types

        if not bool(sr.get("bearer_unit_auto_pass_desperate_escape", False)):
            sr["warp_stalkers_added_auto_pass_desperate_escape"] = True
        sr["bearer_unit_auto_pass_desperate_escape"] = True
        sr["warp_stalkers_active"] = True
        sr["warp_stalkers_expires_phase"] = "MOVEMENT_PHASE" if phase_name == "movement phase" else "CHARGE_PHASE"
        sr["warp_stalkers_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["warp_stalkers_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["warp_stalkers_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        print(f"INFO: WARP STALKERS: {getattr(root, 'name', 'Unit')} can move through enemy models this phase.")
        return True

    def _is_vessels_of_wrath(self) -> bool:
        mgr = self._get_world_eaters_mgr()
        checker = getattr(mgr, "is_vessels_of_wrath", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _vessels_unit_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            try:
                if bool(has_keyword(key)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword(key))
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def _is_daemon_prince_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._vessels_unit_has_keyword(root, "DAEMON PRINCE"):
            return True
        name = self._possessed_normalized_name(root)
        return "daemon prince" in name

    def _is_vessels_infantry_mounted_daemon_prince_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._vessels_unit_has_keyword(root, "INFANTRY"):
            return True
        if self._vessels_unit_has_keyword(root, "MOUNTED"):
            return True
        return self._is_daemon_prince_unit(root)

    def _is_vessels_infantry_daemon_prince_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._vessels_unit_has_keyword(root, "INFANTRY"):
            return True
        return self._is_daemon_prince_unit(root)

    def _is_khorne_berzerkers_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._vessels_unit_has_keyword(root, "BERZERKERS"):
            return True
        name = self._possessed_normalized_name(root)
        return "berzerker" in name

    def _is_khorne_berzerkers_or_jakhals_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._is_khorne_berzerkers_unit(root):
            return True
        if self._vessels_unit_has_keyword(root, "JAKHALS"):
            return True
        name = self._possessed_normalized_name(root)
        return "jakhal" in name

    def _unit_contains_model_keyword(self, unit: Any, keyword: str) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        contains_fn = getattr(root, "_unit_contains_model_with_keyword", None)
        if callable(contains_fn):
            try:
                return bool(contains_fn(key))
            except (AttributeError, TypeError, ValueError):
                return False
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in models:
            if model is None:
                continue
            has_keyword = getattr(model, "has_keyword", None)
            if callable(has_keyword):
                try:
                    if bool(has_keyword(key)):
                        return True
                except (AttributeError, TypeError, ValueError):
                    continue
            has_any_keyword = getattr(model, "has_any_keyword", None)
            if callable(has_any_keyword):
                try:
                    if bool(has_any_keyword(key)):
                        return True
                except (AttributeError, TypeError, ValueError):
                    continue
        return False

    def _is_vessel_of_wrath_unit(self, unit: Any) -> bool:
        return self._unit_contains_model_keyword(unit, "VESSEL OF WRATH")

    def _vessels_on_battlefield(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        return True

    def _vessels_battlefield_candidates(
        self,
        *,
        require_not_fought: bool = False,
        require_target_legal: bool = True,
    ) -> list[Any]:
        if not self._is_vessels_of_wrath():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_world_eaters_mgr()
        candidates: list[Any] = []
        seen: set[str] = set()
        fight_mgr = getattr(self.game, "fight_phase_manager", None) if self.game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or [])
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
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            if not self._vessels_on_battlefield(root):
                continue
            if require_target_legal and not self._is_stratagem_target_legal(root):
                continue
            if require_not_fought:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "fought_this_phase", False)):
                    continue
                if root in fought_units:
                    continue
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _vessels_total_current_wounds(self, unit: Any) -> int:
        root = self._goretrack_root(unit)
        if root is None:
            return 0
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        total = 0
        for model in models:
            if model is None:
                continue
            is_alive_raw = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_raw()) if callable(is_alive_raw) else bool(is_alive_raw)
            if not is_alive:
                continue
            try:
                total += int(getattr(model, "wounds", 0) or 0)
            except (TypeError, ValueError):
                continue
        return int(total)

    def _vessels_in_engagement_range_of_enemy(self, unit: Any, enemy_unit: Any) -> bool:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return False
        root = self._goretrack_root(unit)
        enemy_root = self._goretrack_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        check = getattr(game_map, "is_within_engagement_range", None)
        if not callable(check):
            return False
        try:
            return bool(check(root, enemy_root))
        except (AttributeError, TypeError, ValueError):
            return False

    def _vessels_has_friendly_character_within(self, unit: Any, distance: float) -> bool:
        root = self._goretrack_root(unit)
        if root is None or self.game is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        try:
            from ..utility.aura_utils import unit_within_range_of_unit
        except ImportError:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        mgr = self._get_world_eaters_mgr()
        seen: set[str] = set()
        for unit_candidate in list(getattr(army, "units", []) or []):
            candidate = self._goretrack_root(unit_candidate)
            if candidate is None:
                continue
            uid = self._goretrack_sort_key(candidate)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if candidate is root:
                continue
            if not self._is_unit_alive(candidate):
                continue
            if not self._vessels_on_battlefield(candidate):
                continue
            if not self._is_world_eaters_unit(candidate, mgr=mgr):
                continue
            if not self._vessels_unit_has_keyword(candidate, "CHARACTER"):
                continue
            try:
                if unit_within_range_of_unit(candidate, root, float(distance), use_attached_aggregate=True):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _vessels_objective_candidates(self, unit: Any) -> list[Any]:
        root = self._goretrack_root(unit)
        if root is None or self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        out: list[Any] = []
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control):
                try:
                    update_control(self.game)
                except (AttributeError, TypeError, ValueError):
                    continue
            if getattr(loc, "controlling_player", None) is not self.player:
                continue
            is_within = getattr(root, "is_within_objective_range", None)
            if callable(is_within):
                try:
                    if not bool(is_within(loc)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(objective)
        return out

    def _vessels_target_from_kwargs(self, stratagem_name: str, kwargs: dict[str, Any]) -> tuple[Any, list[Any], Any]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                break
        return unit, candidates, enemy_unit

    def _vessels_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
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
            return True
        return False

    def _queue_world_eaters_vessels_shooting_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_vessels_of_wrath():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._goretrack_owned_by_player(attacking_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return

        targeted_roots: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._goretrack_root(target)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            targeted_roots.append(root)
        if not targeted_roots:
            return

        s_brazen = self.get_by_name("BRAZEN CONTEMPT")
        if (
            s_brazen is not None
            and int(getattr(self.player, "command_points", 0) or 0) >= int(s_brazen.cp_cost or 0)
            and str(s_brazen.name or "").strip().upper() not in self._used_stratagems_this_phase
        ):
            candidates: list[Any] = []
            mgr = self._get_world_eaters_mgr()
            for root in targeted_roots:
                if not self._goretrack_owned_by_player(root, self.player):
                    continue
                if not self._is_unit_alive(root):
                    continue
                if not self._vessels_on_battlefield(root):
                    continue
                if not self._is_world_eaters_unit(root, mgr=mgr):
                    continue
                if not self._is_stratagem_target_legal(root):
                    continue
                candidates.append(root)
            candidates = sorted(candidates, key=self._goretrack_sort_key)
            if candidates and not self._vessels_reaction_already_queued(
                event_name="shooting_targets_selected",
                stratagem_name=s_brazen.name,
                phase_name="Shooting phase",
                enemy_unit=attacking_unit,
            ):
                payload = {
                    "event": "shooting_targets_selected",
                    "phase_name": "Shooting phase",
                    "stratagem": s_brazen.name,
                    "cp_cost": s_brazen.cp_cost,
                    "attacking_unit": attacking_unit,
                    "enemy_unit": attacking_unit,
                    "target_units": list(target_units or []),
                    "candidates": candidates,
                }
                if len(candidates) == 1:
                    payload["target_unit"] = candidates[0]
                self._queue_reaction(payload)

        s_meet = self.get_by_name("MEET FORCE WITH FORCE")
        if s_meet is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(s_meet.cp_cost or 0):
            return
        if str(s_meet.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        mgr = self._get_world_eaters_mgr()
        snapshot_by_unit: dict[str, dict[str, Any]] = {}
        for root in targeted_roots:
            if not self._goretrack_owned_by_player(root, self.player):
                continue
            if not self._is_unit_alive(root):
                continue
            if not self._vessels_on_battlefield(root):
                continue
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            if not self._is_vessels_infantry_mounted_daemon_prince_unit(root):
                continue
            uid = self._goretrack_sort_key(root)
            if not uid:
                continue
            snapshot_by_unit[uid] = {
                "unit": root,
                "wounds_before": self._vessels_total_current_wounds(root),
            }
        if not snapshot_by_unit:
            return
        attacker_key = self._attacker_unit_key(attacking_unit)
        if not attacker_key:
            return
        if not isinstance(getattr(self, "_vessels_meet_force_wounds_before", None), dict):
            self._vessels_meet_force_wounds_before = {}
        self._vessels_meet_force_wounds_before[attacker_key] = snapshot_by_unit

    def _queue_world_eaters_vessels_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
    ) -> None:
        if attacker_unit is None or not self._is_vessels_of_wrath():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        if self._goretrack_owned_by_player(attacker_unit, self.player):
            return
        stratagem = self.get_by_name("MEET FORCE WITH FORCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_key = self._attacker_unit_key(attacker_unit)
        if not attacker_key:
            return
        by_attacker = getattr(self, "_vessels_meet_force_wounds_before", {})
        if not isinstance(by_attacker, dict):
            return
        snapshot_by_unit = by_attacker.pop(attacker_key, {})
        if not isinstance(snapshot_by_unit, dict) or not snapshot_by_unit:
            return
        candidates: list[Any] = []
        wounds_before_by_unit: dict[str, int] = {}
        for uid, entry in snapshot_by_unit.items():
            if not isinstance(entry, dict):
                continue
            root = self._goretrack_root(entry.get("unit"))
            if root is None:
                continue
            if not self._is_unit_alive(root):
                continue
            if not self._vessels_on_battlefield(root):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            if not self._is_vessels_infantry_mounted_daemon_prince_unit(root):
                continue
            wounds_before = int(entry.get("wounds_before", 0) or 0)
            wounds_after = self._vessels_total_current_wounds(root)
            if wounds_after >= wounds_before:
                continue
            candidates.append(root)
            wounds_before_by_unit[str(uid)] = int(wounds_before)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return
        if self._vessels_reaction_already_queued(
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
            "attacking_unit": attacker_unit,
            "candidates": candidates,
            "wounds_before_by_unit": wounds_before_by_unit,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_world_eaters_vessels_move_start_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_vessels_of_wrath():
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        if self._goretrack_owned_by_player(unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("PUNISH THE CRAVEN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_root = self._goretrack_root(unit)
        if enemy_root is None:
            return
        if not self._is_unit_alive(enemy_root):
            return
        if self._vessels_unit_has_keyword(enemy_root, "MONSTER") or self._vessels_unit_has_keyword(enemy_root, "VEHICLE"):
            return
        candidates: list[Any] = []
        for root in self._vessels_battlefield_candidates(require_not_fought=False, require_target_legal=True):
            if not self._is_vessels_infantry_daemon_prince_unit(root):
                continue
            if not self._vessels_in_engagement_range_of_enemy(root, enemy_root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return
        if self._vessels_reaction_already_queued(
            event_name="unit_move_started",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_world_eaters_vessels_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_vessels_of_wrath():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("GORY DEDICATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        tracked = getattr(self, "_vessels_gory_dedication_units", {})
        if not isinstance(tracked, dict) or not tracked:
            return
        mgr = self._get_world_eaters_mgr()
        candidates: list[Any] = []
        for entry in list(tracked.values()):
            root = self._goretrack_root(entry)
            if root is None:
                continue
            if not self._is_unit_alive(root):
                continue
            if not self._vessels_on_battlefield(root):
                continue
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return
        if self._vessels_reaction_already_queued(
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
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _on_model_destroyed_world_eaters_vessels_gory_dedication(
        self,
        *,
        attacker_unit: Any = None,
        target_unit: Any = None,
        weapon_profile: Any = None,
    ) -> None:
        if attacker_unit is None or target_unit is None:
            return
        if not self._is_vessels_of_wrath():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        try:
            if attacker_unit.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        try:
            if attacker_unit.get_parent_army() == target_unit.get_parent_army():
                return
        except (AttributeError, TypeError, ValueError):
            return
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        is_melee = getattr(parent_wargear, "is_melee", None)
        if parent_wargear is not None and callable(is_melee):
            try:
                if not bool(is_melee()):
                    return
            except (AttributeError, TypeError, ValueError):
                return
        root = self._goretrack_root(attacker_unit)
        if root is None or not self._is_world_eaters_unit(root):
            return
        if not isinstance(getattr(self, "_vessels_gory_dedication_units", None), dict):
            self._vessels_gory_dedication_units = {}
        uid = self._goretrack_sort_key(root)
        if uid:
            self._vessels_gory_dedication_units[uid] = root

    def _reset_world_eaters_vessels_phase_start_trackers(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        if isinstance(getattr(self, "_vessels_gory_dedication_units", None), dict):
            self._vessels_gory_dedication_units.clear()

    def _cleanup_world_eaters_vessels_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name == "SHOOTING_PHASE":
            if isinstance(getattr(self, "_vessels_meet_force_wounds_before", None), dict):
                self._vessels_meet_force_wounds_before.clear()

        if phase_name not in ("MOVEMENT_PHASE", "FIGHT_PHASE"):
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
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
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_name == "MOVEMENT_PHASE":
                exp = str(sr.get("enemy_fallback_desperate_escape_expires_phase", "") or "").strip().upper()
                if sr.get("enemy_fallback_desperate_escape") and (not exp or exp == "MOVEMENT_PHASE"):
                    for key in (
                        "enemy_fallback_desperate_escape",
                        "enemy_fallback_desperate_escape_exclude_monster_vehicle",
                        "enemy_fallback_desperate_escape_bs_penalty",
                        "enemy_fallback_desperate_escape_penalty",
                        "enemy_fallback_desperate_escape_target_enemy_id",
                        "enemy_fallback_desperate_escape_expires_phase",
                        "enemy_fallback_desperate_escape_turn_owner",
                        "enemy_fallback_desperate_escape_turn",
                        "enemy_fallback_desperate_escape_source",
                    ):
                        sr.pop(key, None)
            if phase_name == "FIGHT_PHASE":
                exp = str(sr.get("vessels_aspire_to_infamy_expires_phase", "") or "").strip().upper()
                if sr.get("vessels_aspire_to_infamy_active") and (not exp or exp == "FIGHT_PHASE"):
                    for key in (
                        "vessels_aspire_to_infamy_active",
                        "vessels_aspire_to_infamy_strength_bonus",
                        "vessels_aspire_to_infamy_ap_bonus",
                        "vessels_aspire_to_infamy_turn_owner",
                        "vessels_aspire_to_infamy_turn",
                        "vessels_aspire_to_infamy_expires_phase",
                        "vessels_aspire_to_infamy_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("vessels_overshadowed_by_none_expires_phase", "") or "").strip().upper()
                if sr.get("vessels_overshadowed_by_none_active") and (not exp or exp == "FIGHT_PHASE"):
                    for key in (
                        "vessels_overshadowed_by_none_active",
                        "vessels_overshadowed_by_none_turn_owner",
                        "vessels_overshadowed_by_none_turn",
                        "vessels_overshadowed_by_none_expires_phase",
                        "vessels_overshadowed_by_none_source",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _use_world_eaters_vessels_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "ASPIRE TO INFAMY":
            return self._use_vessels_aspire_to_infamy(stratagem, **kwargs)
        if name_u == "OVERSHADOWED BY NONE":
            return self._use_vessels_overshadowed_by_none(stratagem, **kwargs)
        if name_u == "BRAZEN CONTEMPT":
            return self._use_vessels_brazen_contempt(stratagem, **kwargs)
        if name_u == "GORY DEDICATION":
            return self._use_vessels_gory_dedication(stratagem, **kwargs)
        if name_u == "MEET FORCE WITH FORCE":
            return self._use_vessels_meet_force_with_force(stratagem, **kwargs)
        if name_u == "PUNISH THE CRAVEN":
            return self._use_vessels_punish_the_craven(stratagem, **kwargs)
        return None

    def _use_vessels_aspire_to_infamy(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._vessels_target_from_kwargs("ASPIRE TO INFAMY", kwargs)
        if unit is None:
            logger.error("ERROR: ASPIRE TO INFAMY: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_vessels_of_wrath():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ASPIRE TO INFAMY: wrong phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: ASPIRE TO INFAMY: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: ASPIRE TO INFAMY: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._vessels_on_battlefield(root):
            return False
        if not self._is_khorne_berzerkers_or_jakhals_unit(root):
            logger.error("ERROR: ASPIRE TO INFAMY: target must be KHORNE BERZERKERS or JAKHALS")
            return False
        if not self._vessels_has_friendly_character_within(root, 8.0):
            logger.error("ERROR: ASPIRE TO INFAMY: target is not within 8\" of a friendly WORLD EATERS CHARACTER")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: ASPIRE TO INFAMY: target already fought this phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: ASPIRE TO INFAMY: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["vessels_aspire_to_infamy_active"] = True
        sr["vessels_aspire_to_infamy_strength_bonus"] = 1
        sr["vessels_aspire_to_infamy_ap_bonus"] = 1
        sr["vessels_aspire_to_infamy_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["vessels_aspire_to_infamy_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["vessels_aspire_to_infamy_expires_phase"] = "FIGHT_PHASE"
        sr["vessels_aspire_to_infamy_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: ASPIRE TO INFAMY: {getattr(root, 'name', 'Unit')} gains +1S and +1AP (non-CHARACTER models) this phase.")
        return True

    def _use_vessels_overshadowed_by_none(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._vessels_target_from_kwargs("OVERSHADOWED BY NONE", kwargs)
        if unit is None:
            logger.error("ERROR: OVERSHADOWED BY NONE: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_vessels_of_wrath():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: OVERSHADOWED BY NONE: wrong phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: OVERSHADOWED BY NONE: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: OVERSHADOWED BY NONE: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._vessels_on_battlefield(root):
            return False
        if not self._is_vessels_infantry_mounted_daemon_prince_unit(root):
            logger.error("ERROR: OVERSHADOWED BY NONE: target must be INFANTRY, MOUNTED or DAEMON PRINCE")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: OVERSHADOWED BY NONE: target already fought this phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: OVERSHADOWED BY NONE: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["vessels_overshadowed_by_none_active"] = True
        sr["vessels_overshadowed_by_none_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["vessels_overshadowed_by_none_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["vessels_overshadowed_by_none_expires_phase"] = "FIGHT_PHASE"
        sr["vessels_overshadowed_by_none_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: OVERSHADOWED BY NONE: {getattr(root, 'name', 'Unit')} can re-roll Wound rolls vs MONSTER/VEHICLE this phase.")
        return True

    def _use_vessels_brazen_contempt(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, attacking_unit = self._vessels_target_from_kwargs("BRAZEN CONTEMPT", kwargs)
        if unit is None:
            logger.error("ERROR: BRAZEN CONTEMPT: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_vessels_of_wrath():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: BRAZEN CONTEMPT: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: BRAZEN CONTEMPT: not opponent's Shooting phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: BRAZEN CONTEMPT: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: BRAZEN CONTEMPT: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._vessels_on_battlefield(root):
            return False
        if not self._is_world_eaters_unit(root):
            logger.error("ERROR: BRAZEN CONTEMPT: target must be a WORLD EATERS unit")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BRAZEN CONTEMPT: target cannot be selected")
            return False
        if attacking_unit is not None and self._goretrack_owned_by_player(attacking_unit, self.player):
            logger.error("ERROR: BRAZEN CONTEMPT: attacker is not enemy")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        entry = {
            "value": 1,
            "attack_type": "ranged",
            "expires_phase": "SHOOTING_PHASE",
            "source": "Brazen Contempt",
            "requires_strength_gt_toughness": True,
            "requires_strength_gt_toughness_or_unit_contains_keyword": "VESSEL OF WRATH",
        }
        self._append_defensive_effect(root, "defensive_wound_mods", entry)
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: BRAZEN CONTEMPT: {getattr(root, 'name', 'Unit')} gains conditional -1 to be wounded this phase.")
        return True

    def _use_vessels_gory_dedication(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._vessels_target_from_kwargs("GORY DEDICATION", kwargs)
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        if unit is None:
            logger.error("ERROR: GORY DEDICATION: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_vessels_of_wrath():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: GORY DEDICATION: wrong phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: GORY DEDICATION: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: GORY DEDICATION: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._vessels_on_battlefield(root):
            return False
        if not self._is_world_eaters_unit(root):
            logger.error("ERROR: GORY DEDICATION: target must be a WORLD EATERS unit")
            return False
        tracked = getattr(self, "_vessels_gory_dedication_units", {})
        if not isinstance(tracked, dict) or root_id not in tracked:
            logger.error("ERROR: GORY DEDICATION: target did not destroy enemy models with melee attacks this phase")
            return False
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._vessels_objective_candidates(root)
        if objective is None:
            objective = objective_candidates[0] if len(objective_candidates) == 1 else None
        if objective is None:
            logger.error("ERROR: GORY DEDICATION: no objective marker available")
            return False
        if objective_candidates and objective not in objective_candidates:
            logger.error("ERROR: GORY DEDICATION: objective is not eligible")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            return False
        set_sticky = getattr(loc, "set_sticky_control", None)
        if callable(set_sticky):
            set_sticky(self.player, source="gory_dedication")
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "gory_dedication"
            loc.controlling_player = self.player
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: GORY DEDICATION: objective remains under your control until broken.")
        return True

    def _roll_meet_force_with_force_distance(self, unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        base_roll = get_roll("D6")
        can_reroll = bool(self._is_khorne_berzerkers_unit(unit) or self._is_vessel_of_wrath_unit(unit))
        reroll_used = False
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if can_reroll:
            provider = get_decision_provider(self.game, "roll_reroll_provider")
            if callable(provider):
                want = bool(
                    provider(
                        player=player,
                        unit=unit,
                        roll_type="meet_force_with_force",
                        value=int(base_roll or 0),
                        dice=[int(base_roll or 0)],
                        allow_reroll=True,
                        fallback_choice=int(base_roll or 0) <= 3,
                    )
                )
                if want:
                    base_roll = get_roll("D6")
                    reroll_used = True
            else:
                if int(base_roll or 0) <= 3:
                    base_roll = get_roll("D6")
                    reroll_used = True
        if player is not None:
            label = "Meet Force with Force reroll" if reroll_used else "Meet Force with Force roll"
            append_dice(player, f"{label}: {int(base_roll or 0)}\" for {getattr(unit, 'name', 'Unit')}")
        return int(base_roll or 0)

    def _use_vessels_meet_force_with_force(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, enemy_unit = self._vessels_target_from_kwargs("MEET FORCE WITH FORCE", kwargs)
        wounds_before_by_unit = dict(kwargs.get("wounds_before_by_unit") or {})
        if unit is None:
            logger.error("ERROR: MEET FORCE WITH FORCE: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_vessels_of_wrath():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MEET FORCE WITH FORCE: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: MEET FORCE WITH FORCE: not opponent's Shooting phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: MEET FORCE WITH FORCE: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: MEET FORCE WITH FORCE: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._vessels_on_battlefield(root):
            return False
        if not self._is_world_eaters_unit(root):
            logger.error("ERROR: MEET FORCE WITH FORCE: target must be a WORLD EATERS unit")
            return False
        if not self._is_vessels_infantry_mounted_daemon_prince_unit(root):
            logger.error("ERROR: MEET FORCE WITH FORCE: target must be INFANTRY, MOUNTED or DAEMON PRINCE")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MEET FORCE WITH FORCE: target cannot be selected")
            return False
        if enemy_unit is not None and self._goretrack_owned_by_player(enemy_unit, self.player):
            logger.error("ERROR: MEET FORCE WITH FORCE: attacker is not enemy")
            return False
        if not wounds_before_by_unit:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "MEET FORCE WITH FORCE":
                    continue
                wounds_before_by_unit = dict(reaction.get("wounds_before_by_unit") or {})
                break
        if wounds_before_by_unit:
            before = int(wounds_before_by_unit.get(root_id, 0) or 0)
            after = self._vessels_total_current_wounds(root)
            if before and after >= before:
                logger.error("ERROR: MEET FORCE WITH FORCE: target did not lose wounds from this attack")
                return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = self._roll_meet_force_with_force_distance(root)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: MEET FORCE WITH FORCE: movement distance roll failed")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=root,
                attacker_unit=enemy_unit,
                max_distance=int(max_distance),
                kind="meet_force_with_force",
                movement_type="blood_surge",
                source=stratagem.name,
            )
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: MEET FORCE WITH FORCE: {getattr(root, 'name', 'Unit')} can make a Blood Surge move up to {int(max_distance)}\".")
        return True

    def _use_vessels_punish_the_craven(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, enemy_unit = self._vessels_target_from_kwargs("PUNISH THE CRAVEN", kwargs)
        if unit is None:
            logger.error("ERROR: PUNISH THE CRAVEN: no target unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: PUNISH THE CRAVEN: missing enemy unit context")
            return False
        root = self._goretrack_root(unit)
        enemy_root = self._goretrack_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        if not self._is_vessels_of_wrath():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: PUNISH THE CRAVEN: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: PUNISH THE CRAVEN: not opponent's Movement phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: PUNISH THE CRAVEN: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: PUNISH THE CRAVEN: target unit is not yours")
            return False
        if self._goretrack_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PUNISH THE CRAVEN: enemy context is invalid")
            return False
        if not self._is_unit_alive(root) or not self._vessels_on_battlefield(root):
            return False
        if not self._is_unit_alive(enemy_root) or not self._vessels_on_battlefield(enemy_root):
            return False
        if not self._is_world_eaters_unit(root):
            logger.error("ERROR: PUNISH THE CRAVEN: target must be a WORLD EATERS unit")
            return False
        if not self._is_vessels_infantry_daemon_prince_unit(root):
            logger.error("ERROR: PUNISH THE CRAVEN: target must be INFANTRY or DAEMON PRINCE")
            return False
        if self._vessels_unit_has_keyword(enemy_root, "MONSTER") or self._vessels_unit_has_keyword(enemy_root, "VEHICLE"):
            logger.error("ERROR: PUNISH THE CRAVEN: enemy cannot be MONSTER or VEHICLE")
            return False
        if not self._vessels_in_engagement_range_of_enemy(root, enemy_root):
            logger.error("ERROR: PUNISH THE CRAVEN: target must be in Engagement Range of the falling-back unit")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PUNISH THE CRAVEN: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enemy_fallback_desperate_escape"] = True
        sr["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = True
        sr["enemy_fallback_desperate_escape_penalty"] = 1 if self._is_vessel_of_wrath_unit(root) else 0
        sr["enemy_fallback_desperate_escape_target_enemy_id"] = get_entity_id(enemy_root)
        sr["enemy_fallback_desperate_escape_expires_phase"] = "MOVEMENT_PHASE"
        sr["enemy_fallback_desperate_escape_turn_owner"] = str(getattr(active_player, "id", "") or "")
        sr["enemy_fallback_desperate_escape_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["enemy_fallback_desperate_escape_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: PUNISH THE CRAVEN: {getattr(enemy_root, 'name', 'Enemy')} will take Desperate Escape tests when falling back.")
        return True

    def _is_cult_of_blood(self) -> bool:
        mgr = self._get_world_eaters_mgr()
        checker = getattr(mgr, "is_cult_of_blood", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _cult_unit_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword(key)):
            return True
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword(key))
        return False

    def _is_jakhals_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._cult_unit_has_keyword(root, "JAKHALS"):
            return True
        name = self._possessed_normalized_name(root)
        return "jakhal" in name

    def _is_jakhals_or_goremongers_unit(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._is_jakhals_unit(root):
            return True
        if self._cult_unit_has_keyword(root, "GOREMONGERS"):
            return True
        name = self._possessed_normalized_name(root)
        return "goremonger" in name

    def _is_cult_monster_or_titanic_unit(self, unit: Any, *, mgr=None) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if mgr is None:
            mgr = self._get_world_eaters_mgr()
        if not self._is_world_eaters_unit(root, mgr=mgr):
            return False
        if bool(getattr(root, "is_monster", False)) or bool(getattr(root, "is_titanic", False)):
            return True
        if self._cult_unit_has_keyword(root, "MONSTER"):
            return True
        if self._cult_unit_has_keyword(root, "TITANIC"):
            return True
        return False

    def _cult_on_battlefield(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._is_unit_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        return True

    def _cult_battlefield_candidates(
        self,
        *,
        require_target_legal: bool = True,
        require_not_fought: bool = False,
        require_jakhals_or_goremongers: bool = False,
        require_monster_or_titanic: bool = False,
    ) -> list[Any]:
        if not self._is_cult_of_blood():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_world_eaters_mgr()
        fight_mgr = getattr(self.game, "fight_phase_manager", None) if self.game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or [])
        candidates: list[Any] = []
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
            if not self._is_world_eaters_unit(root, mgr=mgr):
                continue
            if not self._cult_on_battlefield(root):
                continue
            if require_target_legal and not self._is_stratagem_target_legal(root):
                continue
            if require_not_fought:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "fought_this_phase", False)):
                    continue
                if root in fought_units:
                    continue
            if require_jakhals_or_goremongers and not self._is_jakhals_or_goremongers_unit(root):
                continue
            if require_monster_or_titanic and not self._is_cult_monster_or_titanic_unit(root, mgr=mgr):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._goretrack_sort_key)

    def _cult_target_from_kwargs(self, stratagem_name: str, kwargs: dict[str, Any]) -> tuple[Any, list[Any], Any]:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                break
        return unit, candidates, enemy_unit

    def _cult_bloodthirsty_horde_candidates(self) -> list[Any]:
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        candidates: list[Any] = []
        for root in self._cult_battlefield_candidates(
            require_not_fought=True,
            require_jakhals_or_goremongers=True,
        ):
            for enemy in list(game_map.get_enemy_units(root) or []):
                enemy_root = self._goretrack_root(enemy)
                if enemy_root is None or not self._is_unit_alive(enemy_root):
                    continue
                if not bool(getattr(enemy_root, "deployed", True)):
                    continue
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    candidates.append(root)
                    break
        return sorted(candidates, key=self._goretrack_sort_key)

    def _cult_brazen_idol_choice_keys(self) -> list[str]:
        mgr = self._get_world_eaters_mgr()
        abilities = list(getattr(mgr, "get_idols_of_khorne_abilities", lambda: [])() or []) if mgr is not None else []
        choice_keys = [
            str(getattr(ability, "key", "") or "").strip().upper()
            for ability in abilities
            if str(getattr(ability, "key", "") or "").strip()
        ]
        return sorted(set(choice_keys))

    def _cult_tool_action_context(self, stratagem_name: str, *, phase_name: str) -> dict[str, Any]:
        name_u = str(stratagem_name or "").strip().upper()
        phase_key = str(phase_name or "").strip().lower()
        if name_u == "BLOODTHIRSTY HORDE":
            if phase_key != "fight phase":
                return {"candidates": []}
            return {"candidates": self._cult_bloodthirsty_horde_candidates()}
        if name_u == "BRAZEN IDOL":
            if phase_key != "command phase" or bool(getattr(self, "_cult_brazen_idol_used", False)):
                return {"candidates": [], "allowed_choice_keys": []}
            return {
                "candidates": self._cult_battlefield_candidates(require_monster_or_titanic=True),
                "allowed_choice_keys": self._cult_brazen_idol_choice_keys(),
            }
        return {}

    def _cult_can_use_tool_action(self, stratagem_name: str, kwargs: dict[str, Any]) -> bool | None:
        name_u = str(stratagem_name or "").strip().upper()
        if name_u not in {"BLOODTHIRSTY HORDE", "BRAZEN IDOL"}:
            return None
        root = self._goretrack_root((kwargs or {}).get("unit") or (kwargs or {}).get("target_unit"))
        if root is None:
            return False
        if name_u == "BLOODTHIRSTY HORDE":
            candidates = self._cult_bloodthirsty_horde_candidates()
            candidate_ids = {self._goretrack_sort_key(candidate) for candidate in list(candidates or [])}
            return self._goretrack_sort_key(root) in candidate_ids
        candidates = self._cult_battlefield_candidates(require_monster_or_titanic=True)
        candidate_ids = {self._goretrack_sort_key(candidate) for candidate in list(candidates or [])}
        if self._goretrack_sort_key(root) not in candidate_ids:
            return False
        idol_key = self._parse_idol_key(
            (kwargs or {}).get("idol_key")
            or (kwargs or {}).get("ability_key")
            or (kwargs or {}).get("selected_idol")
            or (kwargs or {}).get("idol")
            or (kwargs or {}).get("choice_key")
            or (kwargs or {}).get("override_key")
        )
        return bool(idol_key and idol_key in set(self._cult_brazen_idol_choice_keys()))

    def _cult_reaction_already_queued(
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
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit and reaction.get("attacking_unit") is not enemy_unit:
                continue
            if target_unit is not None:
                queued_target = reaction.get("target_unit") or reaction.get("unit")
                if queued_target is not target_unit:
                    continue
            return True
        return False

    def cult_bloody_vengeance_applies(self, attacker_unit: Any, target_unit: Any) -> bool:
        root = self._goretrack_root(attacker_unit)
        target_root = self._goretrack_root(target_unit)
        if root is None or target_root is None:
            return False
        if not self._is_jakhals_or_goremongers_unit(root):
            return False
        enemy_ids = getattr(self, "_cult_bloody_vengeance_enemy_ids", set())
        if not isinstance(enemy_ids, set):
            return False
        target_id = self._goretrack_sort_key(target_root)
        return bool(target_id and target_id in enemy_ids)

    def _queue_world_eaters_cult_shooting_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_cult_of_blood():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        if self._goretrack_owned_by_player(attacking_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("IN THE SHADOW OF BRASS IDOLS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._goretrack_root(target)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._goretrack_owned_by_player(root, self.player):
                continue
            if not self._is_unit_alive(root):
                continue
            if not self._cult_on_battlefield(root):
                continue
            if not self._is_jakhals_or_goremongers_unit(root):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return
        if self._cult_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_world_eaters_cult_fight_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_cult_of_blood():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        if self._goretrack_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("IN THE SHADOW OF BRASS IDOLS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._goretrack_root(target)
            if root is None:
                continue
            uid = self._goretrack_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._goretrack_owned_by_player(root, self.player):
                continue
            if not self._is_unit_alive(root):
                continue
            if not self._cult_on_battlefield(root):
                continue
            if not self._is_jakhals_or_goremongers_unit(root):
                continue
            if not self._is_stratagem_target_legal(root):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._goretrack_sort_key)
        if not candidates:
            return
        if self._cult_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _unit_contains_character_member(self, unit: Any) -> bool:
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if self._cult_unit_has_keyword(root, "CHARACTER"):
            return True
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        for member in members:
            if self._cult_unit_has_keyword(member, "CHARACTER"):
                return True
        return False

    def _queue_world_eaters_cult_unit_destroyed_reactions(
        self,
        *,
        unit: Any,
        destroyed_by_unit: Any = None,
    ) -> None:
        if unit is None or not self._is_cult_of_blood():
            return
        root = self._goretrack_root(unit)
        enemy_root = self._goretrack_root(destroyed_by_unit)
        if root is None:
            return
        if not self._goretrack_owned_by_player(root, self.player):
            return
        if enemy_root is not None and self._goretrack_owned_by_player(enemy_root, self.player):
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase"
        mgr = self._get_world_eaters_mgr()

        bloody = self.get_by_name("BLOODY VENGEANCE")
        if (
            bloody is not None
            and enemy_root is not None
            and int(getattr(self.player, "command_points", 0) or 0) >= int(bloody.cp_cost or 0)
            and str(bloody.name or "").strip().upper() not in self._used_stratagems_this_phase
            and self._is_cult_monster_or_titanic_unit(root, mgr=mgr)
            and not self._is_unit_alive(root)
            and not self._cult_reaction_already_queued(
                event_name="unit_destroyed",
                stratagem_name=bloody.name,
                phase_name=phase_name,
                enemy_unit=enemy_root,
                target_unit=root,
            )
        ):
            self._queue_reaction(
                {
                    "event": "unit_destroyed",
                    "phase_name": phase_name,
                    "stratagem": bloody.name,
                    "cp_cost": bloody.cp_cost,
                    "unit": root,
                    "target_unit": root,
                    "enemy_unit": enemy_root,
                    "candidates": [root],
                }
            )

        drawn = self.get_by_name("DRAWN TO THE SLAUGHTER")
        if drawn is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(drawn.cp_cost or 0):
            return
        if str(drawn.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if bool(getattr(self, "_cult_drawn_to_slaughter_used", False)):
            return
        if self._is_unit_alive(root):
            return
        if not self._is_jakhals_unit(root):
            return
        if self._unit_contains_character_member(root):
            return
        if self._cult_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=drawn.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": phase_name,
                "stratagem": drawn.name,
                "cp_cost": drawn.cp_cost,
                "unit": root,
                "target_unit": root,
                "candidates": [root],
            }
        )

    def _cleanup_world_eaters_cult_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
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
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_name == "FIGHT_PHASE":
                exp = str(sr.get("cult_bloodthirsty_horde_expires_phase", "") or "").strip().upper()
                if sr.get("cult_bloodthirsty_horde_active") and (not exp or exp == "FIGHT_PHASE"):
                    if bool(sr.get("cult_bloodthirsty_horde_added_fight_within_3")):
                        sr.pop("fight_within_3", None)
                    if str(sr.get("fight_within_3_active_source", "") or "").strip() == "Bloodthirsty Horde":
                        sr.pop("fight_within_3_active", None)
                        sr.pop("fight_within_3_active_source", None)
                    for key in (
                        "cult_bloodthirsty_horde_active",
                        "cult_bloodthirsty_horde_expires_phase",
                        "cult_bloodthirsty_horde_turn_owner",
                        "cult_bloodthirsty_horde_turn",
                        "cult_bloodthirsty_horde_source",
                        "cult_bloodthirsty_horde_added_fight_within_3",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("cult_fail_not_blood_god_expires_phase", "") or "").strip().upper()
                if sr.get("cult_fail_not_blood_god_active") and (not exp or exp == "FIGHT_PHASE"):
                    for key in (
                        "cult_fail_not_blood_god_active",
                        "cult_fail_not_blood_god_expires_phase",
                        "cult_fail_not_blood_god_turn_owner",
                        "cult_fail_not_blood_god_turn",
                        "cult_fail_not_blood_god_source",
                    ):
                        sr.pop(key, None)
            exp = str(sr.get("cult_shadow_brass_idols_expires_phase", "") or "").strip().upper()
            if sr.get("cult_shadow_brass_idols_active") and (not exp or exp == phase_name):
                for key in (
                    "cult_shadow_brass_idols_active",
                    "cult_shadow_brass_idols_expires_phase",
                    "cult_shadow_brass_idols_turn_owner",
                    "cult_shadow_brass_idols_turn",
                    "cult_shadow_brass_idols_source",
                ):
                    sr.pop(key, None)
            root.special_rules = sr

    def _parse_idol_key(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        text = text.replace("’", "'")
        text = text.replace("IDOL OF", "").replace("(AURA)", "").strip()
        if "INFINITE RAGE" in text:
            return "INFINITE_RAGE"
        if "BURNING WRATH" in text:
            return "BURNING_WRATH"
        if "BLESSED BLOOD" in text:
            return "BLESSED_BLOOD"
        if text in {"INFINITE_RAGE", "BURNING_WRATH", "BLESSED_BLOOD"}:
            return text
        return ""

    def _clone_drawn_to_slaughter_unit(self, unit: Any) -> Any:
        if unit is None:
            return None
        clone_hook = getattr(unit, "clone_for_cult_ambush", None)
        if callable(clone_hook):
            return clone_hook()
        try:
            from ..units.unit import Unit as UnitClass
        except ImportError:
            return None
        datasheet = getattr(unit, "_datasheet", None)
        if datasheet is None:
            return None
        count = int(getattr(unit, "starting_model_count", 0) or 0)
        if count <= 0:
            count = len(list(getattr(unit, "models", []) or []))
        if count <= 0:
            count = len(list(getattr(unit, "models_lost", []) or []))
        if count <= 0:
            return None
        try:
            new_unit = UnitClass(datasheet, quantity=count, enhancement=getattr(unit, "enhancement", None))
        except TypeError:
            new_unit = UnitClass(datasheet, quantity=count)
        return new_unit

    def _prepare_drawn_to_slaughter_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        set_parent = getattr(unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(army)
        else:
            unit.parent_army = army
        set_reserve = getattr(unit, "set_reserve_status", None)
        if callable(set_reserve):
            set_reserve("strategic_reserves")
        else:
            unit.reserve_status = "strategic_reserves"
        mark_midgame = getattr(unit, "mark_entered_reserves_midgame", None)
        if callable(mark_midgame):
            mark_midgame(game=self.game)
        unit.deployed = True
        unit.reserve_turn_deployed = None
        unit.arrived_from_reserves_this_turn = False
        if hasattr(army, "add_unit"):
            army.add_unit(unit)
        else:
            army.units.append(unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is not None and hasattr(game_map, "units") and unit in game_map.units:
            game_map.units.remove(unit)
        return True

    def _use_world_eaters_cult_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "BLOODTHIRSTY HORDE":
            return self._use_cult_bloodthirsty_horde(stratagem, **kwargs)
        if name_u == "BLOODY VENGEANCE":
            return self._use_cult_bloody_vengeance(stratagem, **kwargs)
        if name_u == "BRAZEN IDOL":
            return self._use_cult_brazen_idol(stratagem, **kwargs)
        if name_u == "DRAWN TO THE SLAUGHTER":
            return self._use_cult_drawn_to_slaughter(stratagem, **kwargs)
        if name_u == "FAIL NOT THE BLOOD GOD":
            return self._use_cult_fail_not_the_blood_god(stratagem, **kwargs)
        if name_u == "IN THE SHADOW OF BRASS IDOLS":
            return self._use_cult_in_the_shadow_of_brass_idols(stratagem, **kwargs)
        return None

    def _use_cult_bloodthirsty_horde(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._cult_target_from_kwargs("BLOODTHIRSTY HORDE", kwargs)
        if unit is None:
            logger.error("ERROR: BLOODTHIRSTY HORDE: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_cult_of_blood():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: BLOODTHIRSTY HORDE: wrong phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: BLOODTHIRSTY HORDE: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: BLOODTHIRSTY HORDE: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._cult_on_battlefield(root):
            return False
        if not self._is_jakhals_or_goremongers_unit(root):
            logger.error("ERROR: BLOODTHIRSTY HORDE: target must be JAKHALS or GOREMONGERS")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: BLOODTHIRSTY HORDE: target already fought this phase")
            return False
        fight_mgr = getattr(self.game, "fight_phase_manager", None) if self.game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or [])
        if root in fought_units:
            logger.error("ERROR: BLOODTHIRSTY HORDE: target already fought this phase")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BLOODTHIRSTY HORDE: target cannot be selected")
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        engaged = False
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._goretrack_root(enemy)
            if enemy_root is None:
                continue
            if not self._is_unit_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            if game_map.is_within_engagement_range(root, enemy_root):
                engaged = True
                break
        if not engaged:
            logger.error("ERROR: BLOODTHIRSTY HORDE: target must be within Engagement Range of an enemy unit")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if not sr.get("fight_within_3"):
            sr["fight_within_3"] = [{"name": "Bloodthirsty Horde"}]
            sr["cult_bloodthirsty_horde_added_fight_within_3"] = True
        sr["fight_within_3_active"] = True
        sr["fight_within_3_active_source"] = "Bloodthirsty Horde"
        sr["cult_bloodthirsty_horde_active"] = True
        sr["cult_bloodthirsty_horde_expires_phase"] = "FIGHT_PHASE"
        sr["cult_bloodthirsty_horde_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["cult_bloodthirsty_horde_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["cult_bloodthirsty_horde_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: BLOODTHIRSTY HORDE: {getattr(root, 'name', 'Unit')} can fight with models within 3\" this phase.")
        return True

    def _use_cult_bloody_vengeance(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, enemy_unit = self._cult_target_from_kwargs("BLOODY VENGEANCE", kwargs)
        if unit is None:
            logger.error("ERROR: BLOODY VENGEANCE: no target unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: BLOODY VENGEANCE: missing enemy unit context")
            return False
        root = self._goretrack_root(unit)
        enemy_root = self._goretrack_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        if not self._is_cult_of_blood():
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: BLOODY VENGEANCE: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: BLOODY VENGEANCE: target unit is not yours")
            return False
        if self._goretrack_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: BLOODY VENGEANCE: enemy context is invalid")
            return False
        if self._is_unit_alive(root):
            logger.error("ERROR: BLOODY VENGEANCE: target unit was not destroyed")
            return False
        if not self._is_cult_monster_or_titanic_unit(root):
            logger.error("ERROR: BLOODY VENGEANCE: target must be a WORLD EATERS MONSTER or TITANIC unit")
            return False
        enemy_id = self._goretrack_sort_key(enemy_root)
        if not enemy_id:
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        if not isinstance(getattr(self, "_cult_bloody_vengeance_enemy_ids", None), set):
            self._cult_bloody_vengeance_enemy_ids = set()
        self._cult_bloody_vengeance_enemy_ids.add(enemy_id)
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: BLOODY VENGEANCE: JAKHALS/GOREMONGERS can re-roll Hit rolls against {getattr(enemy_root, 'name', 'Enemy')} for the battle."
        )
        return True

    def _use_cult_brazen_idol(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._cult_target_from_kwargs("BRAZEN IDOL", kwargs)
        if unit is None:
            logger.error("ERROR: BRAZEN IDOL: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_cult_of_blood():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: BRAZEN IDOL: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            logger.error("ERROR: BRAZEN IDOL: not your turn")
            return False
        if bool(getattr(self, "_cult_brazen_idol_used", False)):
            logger.error("ERROR: BRAZEN IDOL: already used this battle")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: BRAZEN IDOL: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: BRAZEN IDOL: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._cult_on_battlefield(root):
            return False
        if not self._is_cult_monster_or_titanic_unit(root):
            logger.error("ERROR: BRAZEN IDOL: target must be a WORLD EATERS MONSTER or TITANIC unit")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BRAZEN IDOL: target cannot be selected")
            return False
        mgr = self._get_world_eaters_mgr()
        if mgr is None:
            return False
        idol_key = self._parse_idol_key(
            kwargs.get("idol_key")
            or kwargs.get("ability_key")
            or kwargs.get("selected_idol")
            or kwargs.get("idol")
            or kwargs.get("choice_key")
            or kwargs.get("override_key")
        )
        if not idol_key:
            logger.error("ERROR: BRAZEN IDOL: missing or invalid idol selection")
            return False
        abilities = list(getattr(mgr, "get_idols_of_khorne_abilities", lambda: [])() or [])
        valid_keys = {str(getattr(ab, "key", "") or "").strip().upper() for ab in abilities}
        if idol_key not in valid_keys:
            logger.error("ERROR: BRAZEN IDOL: invalid idol selection")
            return False
        activate_source = getattr(mgr, "activate_source_idol_of_khorne", None)
        if not callable(activate_source):
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        if not activate_source(root, idol_key):
            logger.error("ERROR: BRAZEN IDOL: failed to activate source idol override")
            return False
        self._cult_brazen_idol_used = True
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: BRAZEN IDOL: {getattr(root, 'name', 'Unit')} now projects {idol_key} until your next Command phase.")
        return True

    def _use_cult_drawn_to_slaughter(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._cult_target_from_kwargs("DRAWN TO THE SLAUGHTER", kwargs)
        if unit is None:
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_cult_of_blood():
            return False
        if bool(getattr(self, "_cult_drawn_to_slaughter_used", False)):
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: already used this battle")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: target unit is not yours")
            return False
        if self._is_unit_alive(root):
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: target unit was not destroyed")
            return False
        if not self._is_jakhals_unit(root):
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: target must be a JAKHALS unit")
            return False
        if self._unit_contains_character_member(root):
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: cannot return destroyed CHARACTER units to Attached units")
            return False
        cloned = self._clone_drawn_to_slaughter_unit(root)
        if cloned is None:
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: failed to clone destroyed unit")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        if not self._prepare_drawn_to_slaughter_unit(cloned):
            logger.error("ERROR: DRAWN TO THE SLAUGHTER: failed to place cloned unit into Strategic Reserves")
            return False
        self._cult_drawn_to_slaughter_used = True
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: DRAWN TO THE SLAUGHTER: added {getattr(cloned, 'name', 'Unit')} to Strategic Reserves at Starting Strength.")
        return True

    def _use_cult_fail_not_the_blood_god(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, _enemy = self._cult_target_from_kwargs("FAIL NOT THE BLOOD GOD", kwargs)
        if unit is None:
            logger.error("ERROR: FAIL NOT THE BLOOD GOD: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        if root is None:
            return False
        if not self._is_cult_of_blood():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: FAIL NOT THE BLOOD GOD: wrong phase")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: FAIL NOT THE BLOOD GOD: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: FAIL NOT THE BLOOD GOD: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._cult_on_battlefield(root):
            return False
        if not self._is_jakhals_or_goremongers_unit(root):
            logger.error("ERROR: FAIL NOT THE BLOOD GOD: target must be JAKHALS or GOREMONGERS")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: FAIL NOT THE BLOOD GOD: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["cult_fail_not_blood_god_active"] = True
        sr["cult_fail_not_blood_god_expires_phase"] = "FIGHT_PHASE"
        sr["cult_fail_not_blood_god_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["cult_fail_not_blood_god_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["cult_fail_not_blood_god_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: FAIL NOT THE BLOOD GOD: {getattr(root, 'name', 'Unit')} gains hit re-roll support this phase.")
        return True

    def _use_cult_in_the_shadow_of_brass_idols(self, stratagem: Any, **kwargs) -> bool:
        unit, candidates, attacking_unit = self._cult_target_from_kwargs("IN THE SHADOW OF BRASS IDOLS", kwargs)
        if unit is None:
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: no target unit provided")
            return False
        root = self._goretrack_root(unit)
        enemy_root = self._goretrack_root(attacking_unit)
        if root is None:
            return False
        if not self._is_cult_of_blood():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: not opponent's Shooting phase")
            return False
        if enemy_root is None:
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: missing enemy attacker context")
            return False
        if self._goretrack_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: attacker is not enemy")
            return False
        candidate_ids = self._candidate_ids(candidates)
        root_id = self._goretrack_sort_key(root)
        if candidate_ids and root_id not in candidate_ids:
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: target was not selected")
            return False
        if not self._goretrack_owned_by_player(root, self.player):
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: target unit is not yours")
            return False
        if not self._is_unit_alive(root) or not self._cult_on_battlefield(root):
            return False
        if not self._is_jakhals_or_goremongers_unit(root):
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: target must be JAKHALS or GOREMONGERS")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: IN THE SHADOW OF BRASS IDOLS: target cannot be selected")
            return False
        if not self._goretrack_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["cult_shadow_brass_idols_active"] = True
        sr["cult_shadow_brass_idols_expires_phase"] = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["cult_shadow_brass_idols_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["cult_shadow_brass_idols_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["cult_shadow_brass_idols_source"] = stratagem.name
        root.special_rules = sr
        self._goretrack_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: IN THE SHADOW OF BRASS IDOLS: {getattr(root, 'name', 'Unit')} gains temporary Feel No Pain.")
        return True
