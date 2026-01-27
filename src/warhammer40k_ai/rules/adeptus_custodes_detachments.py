from __future__ import annotations

from typing import Iterable, Optional

from ..utility import aura_utils
from ..utility.entity_ids import maybe_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptusCustodesDetachmentManager(DetachmentManagerBase):
    faction_id = "AC"

    _AGAINST_ALL_ODDS_RANGE = 6.0

    def is_lions_of_the_emperor(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Lions of the Emperor")

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return False
        return unit.get_parent_army() is self.army

    def _model_is_custodes(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_has_keyword_or_faction(unit, "ADEPTUS CUSTODES", faction_id=self.faction_id)

    def _unit_is_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        if bool(getattr(unit, "is_vehicle", False)):
            return True
        return self._unit_has_keyword(unit, "VEHICLE")

    def _root_unit(self, unit):
        if unit is None:
            return None
        if hasattr(unit, "get_attached_unit_root"):
            return unit.get_attached_unit_root()
        return unit

    def _unit_key(self, unit) -> Optional[str]:
        if unit is None:
            return None
        return maybe_entity_id(unit) or str(id(unit))

    def _resolve_game_map(self, *, game=None, game_map=None):
        if game_map is not None:
            return game_map
        if game is not None:
            resolved = getattr(game, "map", None)
            if resolved is not None:
                return resolved
        player = getattr(self.army, "player", None) if self.army is not None else None
        game_obj = getattr(player, "game", None) if player is not None else None
        return getattr(game_obj, "map", None) if game_obj is not None else None

    def _iter_unique_friendly_roots(self, unit, game_map) -> Iterable:
        if unit is None or game_map is None or not hasattr(game_map, "get_friendly_units"):
            return ()
        source_root = self._root_unit(unit)
        source_key = self._unit_key(source_root)
        seen = {source_key} if source_key else set()
        for friendly in list(game_map.get_friendly_units(source_root) or []):
            root = self._root_unit(friendly)
            if root is source_root:
                continue
            key = self._unit_key(root)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            if root is not None:
                yield root

    def _has_other_friendly_within_range(self, unit, *, radius: float, game_map) -> bool:
        source_root = self._root_unit(unit)
        if source_root is None or game_map is None:
            return False
        for other_root in self._iter_unique_friendly_roots(source_root, game_map):
            if aura_utils.unit_within_range_of_unit(
                source_root,
                other_root,
                radius,
                use_attached_aggregate=True,
            ):
                return True
        return False

    def against_all_odds_applies(self, model, target_unit=None, *, game=None, game_map=None) -> bool:
        if not self.is_lions_of_the_emperor():
            return False
        if model is None:
            return False
        if not self._model_in_army(model):
            return False
        if not self._model_is_custodes(model):
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or self._unit_is_vehicle(unit):
            return False
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return False
        return not self._has_other_friendly_within_range(
            unit,
            radius=self._AGAINST_ALL_ODDS_RANGE,
            game_map=resolved_map,
        )

    def against_all_odds_hit_bonus(self, model, target_unit=None, *, game=None, game_map=None) -> int:
        if not self.against_all_odds_applies(model, target_unit, game=game, game_map=game_map):
            return 0
        return 1

    def against_all_odds_wound_bonus(self, model, target_unit=None, *, game=None, game_map=None) -> int:
        if not self.against_all_odds_applies(model, target_unit, game=game, game_map=game_map):
            return 0
        return 1
