from __future__ import annotations

from typing import Optional

from ..utility.ability_support import ABILITY_SYNAPSE, army_has_ability_id
from ..utility.aura_utils import unit_within_range_of_unit


class SynapseManager:
    """
    Tyranids army rule: Synapse.
    """

    def __init__(self, army=None):
        self.army = army

    def _army_has_synapse(self) -> bool:
        army = self.army
        if army is None:
            return False
        try:
            faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "TYR":
            return False
        if army_has_ability_id(army, ABILITY_SYNAPSE):
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

    def _unit_is_synapse_source(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_tyranids(unit):
            return False
        try:
            if not unit.has_any_keyword("SYNAPSE"):
                return False
        except Exception:
            return False
        return self._unit_on_battlefield(unit)

    def get_synapse_sources(self) -> list:
        if not self._army_has_synapse():
            return []
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_is_synapse_source(unit):
                sources.append(unit)
        return sources

    def unit_within_synapse_sources(self, unit, *, game=None, game_map=None) -> bool:
        if not self._army_has_synapse():
            return False
        if unit is None:
            return False
        sources = self.get_synapse_sources()
        if not sources:
            return False
        for source in sources:
            try:
                if unit_within_range_of_unit(source, unit, 6.0, use_attached_aggregate=True):
                    return True
            except Exception:
                continue
        return False

    def unit_in_synapse_range(self, unit, *, game=None, game_map=None) -> bool:
        if unit is None:
            return False
        if not self._army_has_synapse():
            return False
        if not self._unit_is_tyranids(unit):
            return False
        if not self._unit_on_battlefield(unit):
            return False
        return self.unit_within_synapse_sources(unit, game=game, game_map=game_map)
