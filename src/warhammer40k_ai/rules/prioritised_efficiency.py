from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shapely.geometry import Point as _ShPoint

from ..utility.ability_support import ABILITY_PRIORITISED_EFFICIENCY, army_has_ability_id


@dataclass(frozen=True)
class EfficiencyMode:
    key: str
    name: str


HOSTILE_ACQUISITION = EfficiencyMode(
    key="HOSTILE_ACQUISITION",
    name="Hostile Acquisition",
)
FORTIFY_TAKEOVER = EfficiencyMode(
    key="FORTIFY_TAKEOVER",
    name="Fortify Takeover",
)


class PrioritisedEfficiencyManager:
    """
    Leagues of Votann army rule: Prioritised Efficiency.

    Tracks Yield Points and the active mode (Hostile Acquisition or Fortify Takeover).
    """

    def __init__(self, army=None):
        self.army = army
        self.yield_points: int = 0
        self.mode: EfficiencyMode = HOSTILE_ACQUISITION
        self.last_mode_turn: Optional[int] = None
        self.last_gain_turn: Optional[int] = None

    def _army_has_rule(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_PRIORITISED_EFFICIENCY)

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def get_mode_name(self) -> str:
        return getattr(self.mode, "name", "") or ""

    def is_hostile_acquisition(self) -> bool:
        return self.mode.key == HOSTILE_ACQUISITION.key

    def is_fortify_takeover(self) -> bool:
        return self.mode.key == FORTIFY_TAKEOVER.key

    def _battle_round(self, game) -> int:
        if game is None:
            return 0
        try:
            return int(getattr(game, "get_battle_round", None)() or 0)
        except Exception:
            try:
                return int(getattr(game, "turn", 0) or 0)
            except Exception:
                return 0

    def _iter_objectives(self, game):
        try:
            objectives = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        except Exception:
            objectives = []
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            if loc is None:
                continue
            if getattr(loc, "removed", False):
                continue
            yield obj, loc

    def _models_for_objective_check(self, unit) -> list:
        try:
            models = list(unit.get_models_for_collision() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        return [m for m in models if bool(getattr(m, "is_alive", True))]

    def _unit_within_objective(self, unit, loc) -> bool:
        if unit is None or loc is None:
            return False
        models = self._models_for_objective_check(unit)
        if not models:
            return False
        try:
            area = _ShPoint(loc.x, loc.y).buffer(loc.control_radius)
        except Exception:
            area = None
        for model in models:
            try:
                if area is not None:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return True
                else:
                    raise ValueError("no area")
            except Exception:
                try:
                    pos = model.get_location()
                except Exception:
                    pos = None
                if not pos:
                    continue
                try:
                    dx = float(pos[0]) - float(loc.x)
                    dy = float(pos[1]) - float(loc.y)
                    radius = float(getattr(loc, "control_radius", 0.0) or 0.0)
                    base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                    if (dx * dx + dy * dy) ** 0.5 <= (radius + base_r):
                        return True
                except Exception:
                    continue
        return False

    def _unit_within_any_objective(self, unit, game) -> bool:
        if unit is None or game is None:
            return False
        for _obj, loc in self._iter_objectives(game):
            if self._unit_within_objective(unit, loc):
                return True
        return False

    def _unit_within_controlled_objective(self, unit, game) -> bool:
        if unit is None or game is None:
            return False
        player = getattr(getattr(self.army, "player", None), "name", None)
        for obj, loc in self._iter_objectives(game):
            try:
                if hasattr(loc, "update_control"):
                    loc.update_control(game)
            except Exception:
                pass
            ctrl = getattr(loc, "controlling_player", None)
            if ctrl is None:
                continue
            if player is None or getattr(ctrl, "name", None) != player:
                continue
            if self._unit_within_objective(unit, loc):
                return True
        return False

    def gain_yield_points(self, game) -> int:
        if not self._army_has_rule():
            return 0
        if game is None:
            return 0
        player = getattr(self.army, "player", None)
        if player is None:
            return 0

        controlled = []
        for obj, loc in self._iter_objectives(game):
            try:
                if hasattr(loc, "update_control"):
                    loc.update_control(game)
            except Exception:
                pass
            if getattr(loc, "controlling_player", None) is player:
                controlled.append(loc)

        if not controlled:
            return 0

        in_dz = 0
        out_dz = 0
        for loc in controlled:
            try:
                in_dz_flag = bool(getattr(game, "_objective_in_player_deployment", lambda _p, _l: False)(player, loc))
            except Exception:
                in_dz_flag = False
            if in_dz_flag:
                in_dz += 1
            else:
                out_dz += 1

        delta = 0
        if in_dz >= 1:
            delta += 1

        if self._battle_round(game) >= 2:
            if out_dz >= 1:
                delta += 1
            if out_dz >= 2:
                delta += 1

            opponent_counts = []
            try:
                for p in list(getattr(game, "players", []) or []):
                    if p is player:
                        continue
                    count = 0
                    for _obj, loc in self._iter_objectives(game):
                        try:
                            if hasattr(loc, "update_control"):
                                loc.update_control(game)
                        except Exception:
                            pass
                        if getattr(loc, "controlling_player", None) is p:
                            count += 1
                    opponent_counts.append(count)
            except Exception:
                opponent_counts = []
            max_opponent = max(opponent_counts) if opponent_counts else 0
            if len(controlled) > max_opponent:
                delta += 1

        if delta <= 0:
            return 0

        self.yield_points = max(0, int(self.yield_points or 0) + int(delta))
        try:
            turn = self._battle_round(game)
            self.last_gain_turn = int(turn) if turn else self.last_gain_turn
        except Exception:
            pass
        return int(delta)

    def spend_yield_points(self, amount: int) -> bool:
        if not self._army_has_rule():
            return False
        try:
            amount = int(amount or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return False
        if int(self.yield_points or 0) < amount:
            return False
        self.yield_points = max(0, int(self.yield_points) - amount)
        return True

    def update_mode_for_player(self, game, player) -> bool:
        if not self._army_has_rule():
            return False
        if player is None or getattr(self.army, "player", None) is not player:
            return False
        desired = FORTIFY_TAKEOVER if int(self.yield_points or 0) >= 7 else HOSTILE_ACQUISITION
        if desired.key == self.mode.key:
            return False
        self.mode = desired
        try:
            self.last_mode_turn = self._battle_round(game)
        except Exception:
            pass
        return True

    def hit_roll_bonus(self, attacker_unit, target_unit, *, game) -> tuple[int, str]:
        if not self._army_has_rule():
            return 0, ""
        if attacker_unit is None or target_unit is None or game is None:
            return 0, ""
        if not self._unit_in_army(attacker_unit):
            return 0, ""
        if self.is_hostile_acquisition():
            if self._unit_within_any_objective(target_unit, game):
                return 1, "Prioritised Efficiency: Hostile Acquisition (+1 to hit)"
            return 0, ""
        if self.is_fortify_takeover():
            if self._unit_within_controlled_objective(attacker_unit, game):
                return 1, "Prioritised Efficiency: Fortify Takeover (+1 to hit)"
        return 0, ""

    def wound_roll_penalty(self, target_unit, *, strength: int, toughness: int) -> tuple[int, str]:
        if not self._army_has_rule():
            return 0, ""
        if target_unit is None:
            return 0, ""
        if not self._unit_in_army(target_unit):
            return 0, ""
        if not self.is_fortify_takeover():
            return 0, ""
        try:
            if bool(getattr(target_unit, "is_vehicle", False)):
                return 0, ""
        except Exception:
            pass
        try:
            if not (isinstance(strength, int) and isinstance(toughness, int)):
                return 0, ""
            if strength <= toughness:
                return 0, ""
        except Exception:
            return 0, ""
        return -1, "Prioritised Efficiency: Fortify Takeover (-1 to wound)"
