from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_TEMPLAR_VOWS, army_has_ability_id


@dataclass(frozen=True)
class TemplarVow:
    key: str
    name: str
    summary: str


VOW_ABHOR = TemplarVow(
    key="ABHOR_THE_WITCH",
    name="Abhor the Witch, Destroy the Witch",
    summary="Re-roll charge vs PSYKER targets; melee gains [PRECISION] vs PSYKER units.",
)
VOW_ACCEPT = TemplarVow(
    key="ACCEPT_ANY_CHALLENGE",
    name="Accept Any Challenge, No Matter the Odds",
    summary="+1 to wound in melee when Strength <= target Toughness.",
)
VOW_SUFFER = TemplarVow(
    key="SUFFER_NOT_THE_UNCLEAN",
    name="Suffer Not the Unclean to Live",
    summary="Can charge after Falling Back; pile-in/consolidate may end closest to closest enemy unit.",
)
VOW_UPHOLD = TemplarVow(
    key="UPHOLD_THE_HONOUR",
    name="Uphold the Honour of the Emperor",
    summary="INFANTRY units can start Actions after Advancing; sticky objectives on your Command phase end.",
)


class TemplarVowsManager:
    """
    Black Templars Army Rule: choose one Vow at the start of the first battle round.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_vow_key: Optional[str] = None

    def _army_has_vows(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_TEMPLAR_VOWS)

    def _unit_is_adeptus_astartes(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("ADEPTUS ASTARTES")
        except Exception:
            return False

    def _unit_is_psyker(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("PSYKER")
        except Exception:
            return False

    def _unit_is_infantry(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("INFANTRY")
        except Exception:
            return False

    def get_active_vow(self) -> Optional[TemplarVow]:
        if not self.active_vow_key:
            return None
        key = str(self.active_vow_key).strip().upper()
        for vow in (VOW_ABHOR, VOW_ACCEPT, VOW_SUFFER, VOW_UPHOLD):
            if vow.key == key:
                return vow
        return None

    def is_vow_active(self, key: str, *, unit=None) -> bool:
        if not self._army_has_vows():
            return False
        if not self.active_vow_key:
            return False
        if unit is not None and not self._unit_is_adeptus_astartes(unit):
            return False
        return str(self.active_vow_key).strip().upper() == str(key or "").strip().upper()

    def can_reroll_charge_against(self, unit, target_unit) -> bool:
        if not self.is_vow_active(VOW_ABHOR.key, unit=unit):
            return False
        return self._unit_is_psyker(target_unit)

    def melee_precision_against(self, unit, target_unit) -> bool:
        if not self.is_vow_active(VOW_ABHOR.key, unit=unit):
            return False
        return self._unit_is_psyker(target_unit)

    def melee_wound_bonus_applies(self, unit, target_unit, *, strength: int, target_toughness: int) -> bool:
        if not self.is_vow_active(VOW_ACCEPT.key, unit=unit):
            return False
        if not self._unit_is_adeptus_astartes(unit):
            return False
        if not isinstance(strength, int) or not isinstance(target_toughness, int):
            return False
        return int(strength) <= int(target_toughness)

    def can_charge_after_fall_back(self, unit) -> bool:
        return self.is_vow_active(VOW_SUFFER.key, unit=unit)

    def use_closest_enemy_unit_rule(self, unit) -> bool:
        return self.is_vow_active(VOW_SUFFER.key, unit=unit)

    def allow_action_after_advance(self, unit, game) -> bool:
        if not self.is_vow_active(VOW_UPHOLD.key, unit=unit):
            return False
        if not self._unit_is_infantry(unit):
            return False
        if game is None:
            return False
        for flag in ("actions_enabled", "mission_actions_enabled", "mission_has_actions"):
            try:
                enabled = getattr(game, flag)
            except Exception:
                continue
            if enabled is False:
                return False
        return True

    def _unit_within_objective(self, unit, objective_point) -> bool:
        if unit is None or objective_point is None:
            return False
        try:
            if not unit.is_alive() or not getattr(unit, "deployed", False):
                return False
        except Exception:
            return False
        try:
            from shapely.geometry import Point as _ShPoint
            area = _ShPoint(objective_point.x, objective_point.y).buffer(objective_point.control_radius)
        except Exception:
            area = None
        try:
            models = unit.get_models_for_collision()
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in models:
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                if area is not None:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return True
            except Exception:
                pass
            try:
                pos = model.get_location()
            except Exception:
                pos = None
            if pos:
                dx = pos[0] - objective_point.x
                dy = pos[1] - objective_point.y
                try:
                    base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                except Exception:
                    base_r = 1.0
                if (dx * dx + dy * dy) ** 0.5 <= (objective_point.control_radius + base_r):
                    return True
        return False

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if not self.is_vow_active(VOW_UPHOLD.key):
            return
        if game is None or player is None:
            return
        if getattr(player, "army", None) is not self.army:
            return
        try:
            objectives = list(getattr(getattr(game, "map", None), "objectives", []) or [])
        except Exception:
            objectives = []
        if not objectives:
            return

        # Ensure control is up to date before applying sticky objectives.
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            try:
                loc.update_control(game)
            except Exception:
                continue

        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if getattr(loc, "controlling_player", None) is not player:
                continue

            has_qualifying_unit = False
            for unit in list(getattr(self.army, "units", []) or []):
                if not self.is_vow_active(VOW_UPHOLD.key, unit=unit):
                    continue
                if not self._unit_is_infantry(unit):
                    continue
                if self._unit_within_objective(unit, loc):
                    has_qualifying_unit = True
                    break
            if not has_qualifying_unit:
                continue

            try:
                if hasattr(loc, "set_sticky_control"):
                    loc.set_sticky_control(player, source="templar_vows")
                else:
                    loc.sticky_controller = player
                    loc.sticky_source = "templar_vows"
                    loc.controlling_player = player
            except Exception:
                continue

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_vows():
            return
        if int(battle_round or 0) != 1:
            return
        if self.active_vow_key:
            return
        player = None
        try:
            player = getattr(self.army, "player", None)
        except Exception:
            player = None
        is_human = False
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        options = [VOW_ABHOR, VOW_ACCEPT, VOW_SUFFER, VOW_UPHOLD]
        ctx = {"ability": "Templar Vows", "options": [v.name for v in options]}
        choice = None
        try:
            if player is not None:
                choice = player._choose_optional_value("TEMPLAR_VOW", [v.name for v in options], ctx)
        except Exception:
            choice = None
        selected = None
        if isinstance(choice, str):
            for vow in options:
                if vow.name.strip().lower() == choice.strip().lower():
                    selected = vow
                    break
        if selected is None:
            if is_human:
                return
            selected = options[0]
        self.active_vow_key = selected.key
