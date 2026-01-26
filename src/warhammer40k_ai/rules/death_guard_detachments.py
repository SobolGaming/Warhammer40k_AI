from __future__ import annotations

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class DeathGuardDetachmentManager(DetachmentManagerBase):
    faction_id = "DG"
    _WORLD_BLIGHT_SOURCE = "worldblight"

    def is_virulent_vectorium(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Virulent Vectorium")

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        return unit.get_parent_army() is self.army

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "DEATH GUARD", faction_id=self.faction_id)

    def _iter_unique_attached_roots(self):
        if self.army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = unit.get_attached_unit_root()
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            yield root

    def _unit_eligible_for_worldblight(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        if not unit.is_alive():
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if unit.is_battle_shocked():
            return False
        return True

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if not self.is_virulent_vectorium():
            return
        if game is None or player is None:
            return
        if getattr(player, "army", None) is not self.army:
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return

        # Ensure control state is up to date before applying sticky effects.
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)

        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if getattr(loc, "controlling_player", None) is not player:
                continue

            has_eligible_unit = False
            for root in self._iter_unique_attached_roots():
                if not self._unit_eligible_for_worldblight(root):
                    continue
                if root.is_within_objective_range(loc):
                    has_eligible_unit = True
                    break
            if not has_eligible_unit:
                continue

            loc.set_sticky_control(player, source=self._WORLD_BLIGHT_SOURCE)
            loc.worldblight_controller = player
            loc.worldblight_source = self._WORLD_BLIGHT_SOURCE
