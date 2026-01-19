from __future__ import annotations

from typing import Optional

from ..utility.ability_support import ABILITY_SHADOW_IN_THE_WARP, army_has_ability_id
from ..utility.entity_ids import get_entity_id


class ShadowInTheWarpManager:
    """
    Tyranids army rule: Shadow in the Warp.
    """

    def __init__(self, army=None):
        self.army = army
        self.used_this_battle: bool = False

    def _army_has_shadow(self) -> bool:
        army = self.army
        if army is None:
            return False
        try:
            faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "TYR":
            return False
        if army_has_ability_id(army, ABILITY_SHADOW_IN_THE_WARP):
            return True
        if not faction_id:
            for unit in list(getattr(army, "units", []) or []):
                if self._unit_is_tyranids(unit):
                    return True
        return False

    @staticmethod
    def _unit_is_tyranids(unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("TYRANIDS")
        except Exception:
            return False

    @staticmethod
    def _unit_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            return False
        try:
            if bool(getattr(unit, "embarked_in", None)):
                return False
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            pass
        return True

    def _unit_has_shadow(self, unit) -> bool:
        if unit is None:
            return False
        try:
            for ab in (getattr(unit, "possible_abilities", []) or []):
                if str(getattr(ab, "name", "") or "").strip().lower() == "shadow in the warp":
                    return True
        except Exception:
            pass
        return self._unit_is_tyranids(unit)

    def _eligible_shadow_sources(self) -> list:
        out = []
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_shadow(unit) and self._unit_on_battlefield(unit):
                out.append(unit)
        return out

    def can_use_now(self, *, game=None, player=None) -> bool:
        if self.used_this_battle:
            return False
        if not self._army_has_shadow():
            return False
        if game is not None:
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                pname = ""
            if pname and pname != "COMMAND_PHASE":
                return False
        return bool(self._eligible_shadow_sources())

    def _unit_id(self, unit) -> str:
        return get_entity_id(unit)

    def _apply_shadow_test_modifier(self, unit, *, game=None, game_map=None) -> None:
        if unit is None:
            return
        mod = 0
        try:
            synapse_mgr = getattr(self.army, "synapse", None)
        except Exception:
            synapse_mgr = None
        if synapse_mgr is not None:
            try:
                if synapse_mgr.unit_within_synapse_sources(unit, game=game, game_map=game_map):
                    mod -= 1
            except Exception:
                mod = mod
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if mod:
            sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) + int(mod)
            reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            reasons.append("Shadow in the Warp")
            sr["battle_shock_test_modifier_reasons"] = reasons
        sr["shadow_in_the_warp_battleshock"] = True
        unit.special_rules = sr

    def _clear_shadow_test_modifier(self, unit) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        sr.pop("shadow_in_the_warp_battleshock", None)
        sr.pop("battle_shock_test_modifier", None)
        sr.pop("battle_shock_test_modifier_reasons", None)
        unit.special_rules = sr

    def activate(self, *, game=None, player=None) -> bool:
        if not self.can_use_now(game=game, player=player):
            return False
        if game is None:
            try:
                player = player or getattr(self.army, "player", None)
                game = getattr(player, "game", None) if player is not None else None
            except Exception:
                game = None
        if game is None:
            return False

        self.used_this_battle = True

        try:
            enemy_units = list(game.get_enemy_units(player) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return True

        game_map = getattr(game, "map", None)
        seen: set[str] = set()
        for unit in enemy_units:
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            uid = self._unit_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not self._unit_on_battlefield(root):
                continue
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass

            self._apply_shadow_test_modifier(root, game=game, game_map=game_map)
            try:
                root.take_battle_shock_test(getattr(game, "turn", 1))
            finally:
                self._clear_shadow_test_modifier(root)
        return True
