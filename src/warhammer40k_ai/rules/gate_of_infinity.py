from __future__ import annotations

import re
from typing import Optional

from ..utility.ability_support import ABILITY_GATE_OF_INFINITY, army_has_ability_id
from ..utility.entity_ids import get_entity_id


class GateOfInfinityManager:
    """
    Grey Knights army rule: Gate of Infinity.
    """

    def __init__(self, army=None):
        self.army = army
        self._last_gate_window_seq = 0
        self._last_gate_window_turn_owner_id = ""
        self._last_gate_window_battle_round = 0
        self._last_gate_window_max_units = 0
        self._last_gate_window_selected = 0
        self._prescient_consumed_window_seq = 0

    def begin_gate_window(self, *, game=None, turn_owner_id: str = "", max_units: int = 0) -> None:
        self._last_gate_window_seq = int(getattr(self, "_last_gate_window_seq", 0) or 0) + 1
        self._last_gate_window_turn_owner_id = str(turn_owner_id or "")
        try:
            self._last_gate_window_battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            self._last_gate_window_battle_round = 0
        try:
            self._last_gate_window_max_units = max(0, int(max_units or 0))
        except Exception:
            self._last_gate_window_max_units = 0
        self._last_gate_window_selected = 0
        self._prescient_consumed_window_seq = 0

    def record_gate_selection_count(self, count: int = 1) -> None:
        try:
            delta = max(0, int(count or 0))
        except Exception:
            delta = 0
        self._last_gate_window_selected = int(getattr(self, "_last_gate_window_selected", 0) or 0) + delta

    def can_offer_prescient_redeployment(self, *, current_player_id: str = "", battle_round: int = 0) -> bool:
        try:
            round_num = int(battle_round or 0)
        except Exception:
            round_num = 0
        if round_num < 2:
            return False
        seq = int(getattr(self, "_last_gate_window_seq", 0) or 0)
        if seq <= 0:
            return False
        if int(getattr(self, "_prescient_consumed_window_seq", 0) or 0) == seq:
            return False
        max_units = int(getattr(self, "_last_gate_window_max_units", 0) or 0)
        selected = int(getattr(self, "_last_gate_window_selected", 0) or 0)
        if max_units <= 0 or selected >= max_units:
            return False
        turn_owner_id = str(getattr(self, "_last_gate_window_turn_owner_id", "") or "")
        if turn_owner_id and str(current_player_id or "") == turn_owner_id:
            return False
        return True

    def mark_prescient_redeployment_consumed(self) -> None:
        self._prescient_consumed_window_seq = int(getattr(self, "_last_gate_window_seq", 0) or 0)

    def _army_has_gate(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "GK":
            return False
        return army_has_ability_id(self.army, ABILITY_GATE_OF_INFINITY)

    def _unit_has_gate(self, unit) -> bool:
        if unit is None:
            return False
        abilities = list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])
        for ab in abilities:
            try:
                checker = getattr(unit, "_ability_is_active", None)
                if callable(checker) and not bool(checker(ab)):
                    continue
            except Exception:
                pass
            try:
                if isinstance(ab, str):
                    name = ab
                    ab_id = ""
                    desc = ab
                else:
                    name = getattr(ab, "name", "")
                    ab_id = getattr(ab, "id", "")
                    desc = getattr(ab, "description", "")
                if str(ab_id or "").strip() == ABILITY_GATE_OF_INFINITY:
                    return True
                if "gate of infinity" in str(name or "").lower():
                    return True
                text = str(f"{name} {desc}" or "").strip().lower()
                text = re.sub(r"\s+", " ", text)
                if re.search(
                    r"\b(?:have|has)\s+(?:the\s+)?(?:deep\s+strike\s+and\s+)?teleport\s+assault\s+abilit(?:y|ies)\b",
                    text,
                ):
                    return True
            except Exception:
                continue
        return False

    def _attached_unit_has_gate(self, unit) -> bool:
        if unit is None:
            return False
        try:
            members = list(unit.get_attached_unit_members() or [])
        except Exception:
            members = [unit]
        for m in members:
            if not self._unit_has_gate(m):
                return False
        return True

    def _unit_is_available(self, unit, game_map) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        try:
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        if game_map is None:
            return False
        try:
            if hasattr(game_map, "units") and unit not in game_map.units:
                return False
        except Exception:
            pass
        try:
            enemies = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            enemies = []
        for enemy in enemies:
            try:
                if not getattr(enemy, "is_alive", lambda: True)():
                    continue
            except Exception:
                continue
            try:
                if game_map.is_within_engagement_range(unit, enemy):
                    return False
            except Exception:
                continue
        return True

    def get_max_units_for_battlefield(self, game=None) -> int:
        try:
            size = getattr(getattr(game, "battlefield", None), "size", None)
        except Exception:
            size = None
        if size is None:
            return 0
        try:
            from ..engine.battlefield import BattlefieldSize
        except Exception:
            BattlefieldSize = None
        if BattlefieldSize is not None:
            if size == BattlefieldSize.INCURSION:
                return 2
            if size == BattlefieldSize.STRIKE_FORCE:
                return 3
            if size == BattlefieldSize.ONSLAUGHT:
                return 4
        return 0

    def get_eligible_units(self, *, game=None, player=None) -> list:
        if not self._army_has_gate():
            return []
        if player is None:
            player = getattr(self.army, "player", None)
        if game is None and player is not None:
            try:
                game = player.game
            except Exception:
                game = None
        if player is None or game is None:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []

        out = []
        seen = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            try:
                uid = get_entity_id(root)
            except Exception:
                uid = ""
            if uid in seen:
                continue
            seen.add(uid)
            if not self._attached_unit_has_gate(root):
                continue
            if not self._unit_is_available(root, game_map):
                continue
            out.append(root)
        return out

    def send_units_to_strategic_reserves(self, units, *, game=None, reason: str = "") -> list:
        moved = []
        game_map = getattr(game, "map", None) if game is not None else None
        for unit in list(units or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            try:
                members = list(root.get_attached_unit_members() or [])
            except Exception:
                members = [root]
            for member in members:
                try:
                    if hasattr(member, "set_reserve_status"):
                        member.set_reserve_status("strategic_reserves")
                    else:
                        member.reserve_status = "strategic_reserves"
                except Exception:
                    pass
                try:
                    if hasattr(member, "mark_entered_reserves_midgame"):
                        member.mark_entered_reserves_midgame(game=game)
                except Exception:
                    pass
                try:
                    if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                        if game is not None:
                            member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1
                except Exception:
                    pass
                try:
                    member.deployed = True
                    member.reserve_turn_deployed = None
                    member.arrived_from_reserves_this_turn = False
                except Exception:
                    pass
                try:
                    if game_map is not None and hasattr(game_map, "units") and member in game_map.units:
                        game_map.units.remove(member)
                except Exception:
                    pass
            moved.append(root)
        if str(reason or "").strip().lower() == "gate_of_infinity" and moved:
            self.record_gate_selection_count(len(moved))
        return moved

    def auto_gate_units(self, *, game=None, player=None) -> list:
        """No-op: Gate of Infinity requires explicit player selection."""
        return []
