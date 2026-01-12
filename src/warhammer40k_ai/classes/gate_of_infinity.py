from __future__ import annotations

import random
from typing import Optional

from ..utility.ability_support import ABILITY_GATE_OF_INFINITY, army_has_ability_id


class GateOfInfinityManager:
    """
    Grey Knights army rule: Gate of Infinity.
    """

    def __init__(self, army=None):
        self.army = army

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
                if isinstance(ab, str):
                    name = ab
                    ab_id = ""
                else:
                    name = getattr(ab, "name", "")
                    ab_id = getattr(ab, "id", "")
                if str(ab_id or "").strip() == ABILITY_GATE_OF_INFINITY:
                    return True
                if "gate of infinity" in str(name or "").lower():
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
            if getattr(unit, "is_embarked", None) and callable(unit.is_embarked) and bool(unit.is_embarked()):
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
            from .game import BattlefieldSize
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
                uid = getattr(root, "_id", id(root))
            except Exception:
                uid = id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not self._attached_unit_has_gate(root):
                continue
            if not self._unit_is_available(root, game_map):
                continue
            out.append(root)
        return out

    def send_units_to_strategic_reserves(self, units, *, game=None) -> list:
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
        return moved

    def auto_gate_units(self, *, game=None, player=None) -> list:
        if game is None:
            return []
        max_units = self.get_max_units_for_battlefield(game)
        if max_units <= 0:
            return []
        try:
            eligible = list(self.get_eligible_units(game=game, player=player) or [])
        except Exception:
            eligible = []
        if not eligible:
            return []
        random.shuffle(eligible)
        chosen = eligible[: int(max_units)]
        self.send_units_to_strategic_reserves(chosen, game=game)
        return chosen
