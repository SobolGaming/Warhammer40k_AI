from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_NURGLES_GIFT, army_has_ability_id
from ..utility.aura_effects import nurgles_gift_contagion_range
from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class NurglesPlague:
    key: str
    name: str
    summary: str


PLAGUE_SKULLSQUIRM = NurglesPlague(
    key="SKULLSQUIRM_BLIGHT",
    name="Skullsquirm Blight",
    summary="Afflicted units suffer -1 to Hit rolls.",
)
PLAGUE_RATTLEJOINT = NurglesPlague(
    key="RATTLEJOINT_AGUE",
    name="Rattlejoint Ague",
    summary="Afflicted units worsen their Save characteristic by 1.",
)
PLAGUE_SCABROUS = NurglesPlague(
    key="SCABROUS_SOULROT",
    name="Scabrous Soulrot",
    summary="Afflicted units worsen Move, Leadership, and OC by 1 (OC min 1).",
)

DEFAULT_PLAGUES: tuple[NurglesPlague, ...] = (
    PLAGUE_SKULLSQUIRM,
    PLAGUE_RATTLEJOINT,
    PLAGUE_SCABROUS,
)


class NurglesGiftManager:
    """
    Death Guard army rule: Nurgle's Gift (Aura) + selected Plague.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_plague_key: Optional[str] = None

    def _army_has_gift(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_NURGLES_GIFT)

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("DEATH GUARD")
        except Exception:
            return False

    def _unit_is_valid_contagion_source(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_death_guard(unit):
            return False
        try:
            if not bool(getattr(unit, "deployed", False)):
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive):
                return bool(unit.is_alive())
        except Exception:
            return False
        return True

    def get_contagion_range(self, battle_round: int) -> float:
        return float(nurgles_gift_contagion_range(battle_round))

    def get_active_plague(self) -> Optional[NurglesPlague]:
        if not self.active_plague_key:
            return None
        key = str(self.active_plague_key).strip().upper()
        for plague in DEFAULT_PLAGUES:
            if plague.key == key:
                return plague
        return None

    def is_plague_active(self, key: str) -> bool:
        if not self._army_has_gift():
            return False
        if not self.active_plague_key:
            return False
        return str(self.active_plague_key).strip().upper() == str(key or "").strip().upper()

    def on_declare_battle_formations_start(self, *, game=None) -> None:
        if not self._army_has_gift():
            return
        if self.active_plague_key:
            return

        player = None
        try:
            player = getattr(self.army, "player", None)
        except Exception:
            player = None

        options = list(DEFAULT_PLAGUES)
        ctx = {"ability": "Nurgle's Gift (Aura)", "options": [p.name for p in options]}
        choice = None
        try:
            if player is not None:
                choice = player._choose_optional_value("NURGLE_PLAGUE", [p.name for p in options], ctx)
        except Exception:
            choice = None

        selected = None
        if choice in options:
            selected = choice
        elif isinstance(choice, str):
            choice_norm = choice.strip().lower()
            for plague in options:
                if plague.name.strip().lower() == choice_norm or plague.key.strip().lower() == choice_norm:
                    selected = plague
                    break

        if selected is not None:
            self.active_plague_key = selected.key

    def is_unit_afflicted(self, unit, *, game=None, game_map=None) -> bool:
        return self.get_afflicted_plague_for_unit(unit, game=game, game_map=game_map) is not None

    @staticmethod
    def get_afflicted_plague_for_unit(unit, *, game=None, game_map=None) -> Optional[NurglesPlague]:
        if unit is None:
            return None
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive):
                if not unit.is_alive():
                    return None
        except Exception:
            pass
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return None
        except Exception:
            pass

        if game_map is None:
            if game is None:
                try:
                    army = unit.get_parent_army()
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
            if game is not None:
                game_map = getattr(game, "map", None)
        if game_map is None:
            return None

        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0

        try:
            enemy_units = list(game_map.get_enemy_units(unit))
        except Exception:
            try:
                unit_army = unit.get_parent_army()
            except Exception:
                unit_army = None
            try:
                enemy_units = [
                    u for u in list(getattr(game_map, "units", []) or [])
                    if getattr(u, "get_parent_army", lambda: None)() is not unit_army
                ]
            except Exception:
                enemy_units = []

        if not enemy_units:
            return None

        from ..utility import aura_utils as _aura_utils

        checked_armies: set[str] = set()
        for enemy in enemy_units:
            try:
                enemy_army = enemy.get_parent_army()
            except Exception:
                enemy_army = None
            if enemy_army is None:
                continue
            try:
                key = get_entity_id(enemy_army)
            except Exception:
                key = ""
            if key in checked_armies:
                continue
            checked_armies.add(key)

            mgr = getattr(enemy_army, "nurgles_gift", None)
            if mgr is None:
                continue
            if not getattr(mgr, "_army_has_gift", lambda: False)():
                continue
            plague = mgr.get_active_plague()
            if plague is None:
                continue

            rng = mgr.get_contagion_range(br)
            try:
                sources = list(getattr(enemy_army, "units", []) or [])
            except Exception:
                sources = [u for u in enemy_units if getattr(u, "get_parent_army", lambda: None)() is enemy_army]

            for source in sources:
                if not mgr._unit_is_valid_contagion_source(source):
                    continue
                if _aura_utils.unit_within_range_of_unit(source, unit, rng, use_attached_aggregate=True):
                    return plague

            # Virulent Vectorium: Worldblight turns controlled objectives into contagion sources.
            objectives = list(getattr(game_map, "objectives", []) or [])
            for obj in objectives:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                worldblight_owner = getattr(loc, "worldblight_controller", None)
                if worldblight_owner is None:
                    continue
                if getattr(worldblight_owner, "army", None) is not enemy_army:
                    continue
                if (
                    getattr(loc, "controlling_player", None) is not worldblight_owner
                    and getattr(loc, "sticky_controller", None) is not worldblight_owner
                ):
                    continue
                if _aura_utils.unit_within_range_of_point_3d(unit, (loc.x, loc.y), rng, use_attached_aggregate=True):
                    return plague

        return None
