from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_TEMPLAR_VOWS, army_has_ability_id
import re


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
        if not army_has_ability_id(self.army, ABILITY_TEMPLAR_VOWS):
            return False
        return self._army_is_black_templars()

    def _army_is_black_templars(self) -> bool:
        if self.army is None:
            return False
        try:
            mgr = getattr(self.army, "space_marines_detachments", None)
            if mgr is not None and getattr(mgr, "get_committed_chapter_keyword", lambda: None)() == "BLACK TEMPLARS":
                return True
        except Exception:
            pass
        try:
            for unit in list(getattr(self.army, "units", []) or []):
                if unit.has_any_keyword("BLACK TEMPLARS"):
                    return True
        except Exception:
            pass
        def _norm(text: str) -> str:
            t = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
            return re.sub(r"\s+", " ", t).strip()
        try:
            if _norm(getattr(self.army, "faction", "")) == "black templars":
                return True
        except Exception:
            pass
        try:
            has_detachment = getattr(self.army, "has_detachment_type", None)
            if callable(has_detachment) and has_detachment("Black Templars", "Righteous Crusaders"):
                return True
        except Exception:
            pass
        try:
            if not hasattr(self.army, "space_marines_detachments"):
                faction = str(getattr(self.army, "faction", "") or "").strip()
                primary_detachment = getattr(self.army, "get_primary_detachment_type", None)
                if callable(primary_detachment):
                    detachment = str(primary_detachment() or "").strip()
                else:
                    detachment = ""
                if not faction and not detachment:
                    try:
                        from .space_marines_detachments import CHAPTER_KEYWORD_MAP
                        other_chapters = {kw for kw in CHAPTER_KEYWORD_MAP.values() if kw != "BLACK TEMPLARS"}
                    except Exception:
                        other_chapters = {"BLOOD ANGELS", "DARK ANGELS", "DEATHWATCH", "SPACE WOLVES"}
                    units = list(getattr(self.army, "units", []) or [])
                    has_other_chapter = False
                    for unit in units:
                        for kw in other_chapters:
                            try:
                                if unit.has_any_keyword(kw):
                                    has_other_chapter = True
                                    break
                            except Exception:
                                continue
                        if has_other_chapter:
                            break
                    if not has_other_chapter:
                        return True
        except Exception:
            pass
        return False

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
        if game is not None:
            if not bool(getattr(game, "is_authoritative", True)):
                return
            try:
                from ..engine.decision_kinds import DECISION_CHOOSE_VOW
                from ..engine.decisions import DecisionOption, DecisionRequest
                from ..utility.entity_ids import get_entity_id
            except Exception:
                return
            army_id = get_entity_id(self.army) if self.army is not None else None
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_VOW:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("army_id", "")) == str(army_id):
                        return
            options = [VOW_ABHOR, VOW_ACCEPT, VOW_SUFFER, VOW_UPHOLD]
            req_options = []
            player_id = str(getattr(player, "id", "") or "") if player is not None else ""
            for vow in options:
                req_options.append(
                    DecisionOption.create(
                        vow.name,
                        payload={
                            "choice_key": vow.key,
                            "summary": vow.summary,
                            "army_id": army_id,
                            "ability": "templar_vow",
                            "ability_name": "Templar Vows",
                            "battle_round": int(battle_round),
                            "player_id": player_id,
                        },
                    )
                )
            if not req_options:
                return
            req = DecisionRequest.create(
                DECISION_CHOOSE_VOW,
                "Select a Templar Vow.",
                player_id=getattr(player, "id", None) if player is not None else None,
                options=req_options,
                context={
                    "ability": "templar_vow",
                    "ability_name": "Templar Vows",
                    "army_id": army_id,
                    "battle_round": int(battle_round),
                    "player_id": player_id,
                },
            )
            if hasattr(game, "request_decision"):
                game.request_decision(req)
            return
        return
