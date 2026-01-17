from __future__ import annotations

from ..utility.ability_support import ABILITY_WAAAGH, army_has_ability_id


class WaaaghManager:
    """
    Orks army rule: Waaagh!

    Once per battle, at the start of your Command phase, you can call a Waaagh!
    Until the start of your next Command phase, units with this ability:
      - can charge after advancing,
      - get +1 Strength and +1 Attacks to melee weapons,
      - gain a 5+ invulnerable save.
    """

    def __init__(self, army=None):
        self.army = army
        self.active: bool = False
        self.used_this_battle: bool = False
        self.called_turn: int | None = None
        self.called_player = None

    def _army_has_waaagh(self) -> bool:
        army = self.army
        if army is None:
            return False
        try:
            faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "ORK":
            return False
        if army_has_ability_id(army, ABILITY_WAAAGH):
            return True
        if not faction_id:
            for unit in list(getattr(army, "units", []) or []):
                if self._unit_has_waaagh(unit):
                    return True
        return False

    @staticmethod
    def _unit_is_embarked(unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(getattr(unit, "is_embarked", False))
        except Exception:
            return False

    def _unit_has_waaagh(self, unit) -> bool:
        if unit is None:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                if str(getattr(ab, "name", "") or "").strip().lower() == "waaagh!":
                    return True
        except Exception:
            pass
        try:
            if unit.has_any_keyword("ORKS"):
                return True
        except Exception:
            pass
        return False

    def can_call_now(self, *, game=None, player=None) -> bool:
        if self.used_this_battle:
            return False
        if not self._army_has_waaagh():
            return False
        if game is not None:
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                pname = ""
            if pname and pname != "COMMAND_PHASE":
                return False
            if player is not None:
                try:
                    if getattr(game, "get_current_player", lambda: None)() is not player:
                        return False
                except Exception:
                    pass
        return True

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.active:
            return
        if player is None or self.called_player is not player:
            return
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if self.called_turn is None:
            return
        if current_turn > int(self.called_turn):
            self.active = False

    def call_waaagh(self, *, game=None, player=None) -> bool:
        if not self.can_call_now(game=game, player=player):
            return False
        self.used_this_battle = True
        self.active = True
        try:
            self.called_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            self.called_turn = None
        self.called_player = player

        try:
            es = getattr(game, "event_system", None)
            if es is not None:
                units = []
                for unit in list(getattr(self.army, "units", []) or []):
                    if self.unit_is_affected(unit, game=game):
                        units.append(unit)
                es.publish("waaagh_called", player=player, game=game, units=units)
        except Exception:
            pass
        return True

    def unit_is_affected(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if not self.active:
            return False
        if not self._unit_has_waaagh(unit):
            return False
        if self._unit_is_embarked(unit):
            return False
        try:
            if getattr(unit, "get_parent_army", lambda: None)() is not self.army:
                return False
        except Exception:
            pass
        return True
