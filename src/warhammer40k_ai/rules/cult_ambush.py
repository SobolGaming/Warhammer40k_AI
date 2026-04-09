from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_CULT_AMBUSH, army_has_ability_id
from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL
from ..utility.entity_ids import get_entity_id
from ..utility.aura_utils import horizontal_distance_point_to_model_base_2d
from ..utility.model_base import Base, BaseType
from ..utility.rng import resolve_rng


MARKER_RADIUS_INCHES = 0.63  # 32mm diameter marker approx 1.26" across


@dataclass
class CultAmbushMarker:
    marker_id: str
    x: float
    y: float
    z: float = 0.0
    active: bool = True
    pending_relocation: bool = False
    last_moved_turn: int = 0
    last_moved_turn_owner_id: str = ""

    @property
    def id(self) -> str:
        return self.marker_id


class CultAmbushManager:
    """
    Genestealer Cults army rule: Cult Ambush.

    Tracks Resurgence points, Cult Ambush markers, and reinforcements.
    """

    def __init__(self, army=None):
        self.army = army
        self.resurgence_points: int = 0
        self._initialized: bool = False
        self.markers: list[CultAmbushMarker] = []
        self.summon_the_cult_used: bool = False

    def _army_has_rule(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_CULT_AMBUSH)

    def _unit_has_cult_ambush(self, unit) -> bool:
        if unit is None:
            return False
        for ab in list(getattr(unit, "possible_abilities", []) or []):
            try:
                name = str(getattr(ab, "name", "") or "").strip().lower()
            except Exception:
                name = ""
            if name == "cult ambush":
                return True
        return False

    def _unit_has_named_ability(self, unit, ability_name: str) -> bool:
        if unit is None:
            return False
        wanted = str(ability_name or "").strip().lower()
        if not wanted:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            for ab in list(getattr(member, "possible_abilities", []) or []):
                try:
                    name = str(getattr(ab, "name", "") or "").strip().lower()
                except Exception:
                    name = ""
                if name == wanted:
                    return True
        return False

    def _unit_members_all_have_cult_ambush(self, unit) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            return False
        for member in members:
            if not self._unit_has_cult_ambush(member):
                return False
        return True

    def _unit_starting_model_count(self, unit) -> int:
        try:
            return int(getattr(unit, "starting_model_count", 0) or 0)
        except Exception:
            try:
                return len(getattr(unit, "models", []) or [])
            except Exception:
                return 0

    def _unit_is_from_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def _unit_is_alive(self, unit) -> bool:
        try:
            return bool(getattr(unit, "is_alive", lambda: True)())
        except Exception:
            try:
                return any(bool(getattr(m, "is_alive", True)) for m in (getattr(unit, "models", []) or []))
            except Exception:
                return False

    def _unit_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "deployed", False)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            return False
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        return True

    def _tokens_for_battlefield(self, game) -> int:
        size_name = ""
        try:
            size = getattr(getattr(game, "battlefield", None), "size", None)
            size_name = str(getattr(size, "name", "") or size or "")
        except Exception:
            size_name = ""
        size_name = size_name.strip().upper().replace(" ", "_")
        if "INCURSION" in size_name:
            return 6
        if "STRIKE_FORCE" in size_name or "STRIKEFORCE" in size_name:
            return 10
        if "ONSLAUGHT" in size_name:
            return 14
        return 0

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_rule():
            return
        if self._initialized:
            return
        bonus = 0
        gsc_mgr = getattr(self.army, "genestealer_cults_detachments", None) if self.army is not None else None
        bonus_fn = getattr(gsc_mgr, "xenocreed_additional_starting_resurgence_points", None) if gsc_mgr is not None else None
        if callable(bonus_fn):
            try:
                bonus = int(bonus_fn() or 0)
            except (TypeError, ValueError):
                bonus = 0
        self.resurgence_points = int(self._tokens_for_battlefield(game)) + max(0, int(bonus))
        self._initialized = True
        self._publish_update(game)

    def resurgence_cost_for_unit(self, unit) -> Optional[int]:
        if unit is None:
            return None
        name = str(getattr(unit, "name", "") or "").strip().lower()
        name = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in name)
        name = " ".join(name.split())
        starting = self._unit_starting_model_count(unit)
        if not name or starting <= 0:
            return None

        if "aberrant" in name:
            return {5: 4, 10: 8}.get(starting)
        if "acolyte hybrid" in name or "hybrid metamorph" in name:
            return {5: 2, 10: 4}.get(starting)
        if "atalan jackal" in name:
            return {5: 2, 10: 6}.get(starting)
        if "neophyte hybrid" in name:
            return {10: 3, 20: 6}.get(starting)
        if "purestrain genestealer" in name:
            return {5: 2, 10: 6}.get(starting)
        return None

    def can_spend_for_unit(self, unit) -> bool:
        if not self._army_has_rule():
            return False
        if not self._unit_is_from_army(unit):
            return False
        if not self._unit_members_all_have_cult_ambush(unit):
            return False
        cost = self.resurgence_cost_for_unit(unit)
        if cost is None:
            return False
        return int(self.resurgence_points or 0) >= int(cost)

    def _clone_unit(self, unit):
        if unit is None:
            return None
        clone_hook = getattr(unit, "clone_for_cult_ambush", None)
        if callable(clone_hook):
            try:
                return clone_hook()
            except Exception:
                return None
        try:
            from ..units.unit import Unit as UnitClass
        except Exception:
            return None
        datasheet = getattr(unit, "_datasheet", None)
        if datasheet is None:
            return None
        try:
            count = int(getattr(unit, "starting_model_count", 0) or 0)
        except Exception:
            count = 0
        if count <= 0:
            try:
                count = len(getattr(unit, "models", []) or [])
            except Exception:
                count = 0
        if count <= 0:
            return None
        try:
            new_unit = UnitClass(datasheet, quantity=count, enhancement=getattr(unit, "enhancement", None))
        except Exception:
            new_unit = UnitClass(datasheet, quantity=count)
        self._copy_model_wargear(unit, new_unit)
        try:
            new_unit.is_warlord = bool(getattr(unit, "is_warlord", False))
        except Exception:
            pass
        return new_unit

    def _copy_model_wargear(self, source_unit, target_unit) -> None:
        if source_unit is None or target_unit is None:
            return

        def _norm(text: str) -> str:
            raw = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in str(text or "").lower())
            return " ".join(raw.split())

        try:
            source_models = list(getattr(source_unit, "models", []) or [])
        except Exception:
            source_models = []
        try:
            source_models += list(getattr(source_unit, "models_lost", []) or [])
        except Exception:
            pass

        buckets: dict[str, list] = {}
        for sm in source_models:
            key = _norm(getattr(sm, "name", "") or "")
            buckets.setdefault(key, []).append(sm)

        possible = list(getattr(target_unit, "possible_wargear", []) or [])
        possible_by_name = {_norm(getattr(wg, "name", "") or ""): wg for wg in possible}

        leftovers = [sm for sm in source_models if sm is not None]

        for tm in list(getattr(target_unit, "models", []) or []):
            key = _norm(getattr(tm, "name", "") or "")
            src = None
            if key in buckets and buckets[key]:
                src = buckets[key].pop(0)
            elif leftovers:
                src = leftovers.pop(0)
            if src is None:
                continue

            try:
                src_wargear = list(getattr(src, "wargear", []) or [])
            except Exception:
                src_wargear = []
            try:
                tm.wargear = []
            except Exception:
                pass
            for wg in src_wargear:
                try:
                    nm = _norm(getattr(wg, "name", "") or "")
                except Exception:
                    nm = ""
                clone = possible_by_name.get(nm)
                try:
                    if clone is not None:
                        tm.wargear.append(clone)
                    else:
                        tm.wargear.append(wg)
                except Exception:
                    continue
            try:
                tm.optional_wargear = list(getattr(src, "optional_wargear", []) or [])
            except Exception:
                pass

    def _reset_one_shot(self, unit) -> None:
        for m in list(getattr(unit, "models", []) or []):
            try:
                setattr(m, "_one_shot_used", set())
            except Exception:
                pass

    def _prepare_unit_in_cult_ambush(self, unit, *, game=None) -> None:
        if unit is None:
            return
        try:
            unit.set_parent_army(self.army)
        except Exception:
            try:
                unit.parent_army = self.army
            except Exception:
                pass
        try:
            if hasattr(unit, "set_reserve_status"):
                unit.set_reserve_status("strategic_reserves")
            else:
                unit.reserve_status = "strategic_reserves"
        except Exception:
            pass
        try:
            if hasattr(unit, "mark_entered_reserves_midgame"):
                unit.mark_entered_reserves_midgame(game=game)
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_aircraft", False)) and not bool(getattr(unit, "hover_mode", False)):
                if game is not None:
                    unit._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1
        except Exception:
            pass
        try:
            unit.deployed = True
            unit.reserve_turn_deployed = None
            unit.arrived_from_reserves_this_turn = False
        except Exception:
            pass
        try:
            setattr(unit, "_cult_ambush", True)
        except Exception:
            pass
        self._reset_one_shot(unit)

        try:
            if self.army is not None:
                if hasattr(self.army, "add_unit"):
                    self.army.add_unit(unit)
                else:
                    self.army.units.append(unit)
        except Exception:
            pass

        try:
            if game is not None and hasattr(game, "map") and hasattr(game.map, "units"):
                if unit in game.map.units:
                    game.map.units.remove(unit)
        except Exception:
            pass

    def spend_resurgence_for_unit(self, unit, *, game=None) -> Optional[object]:
        if unit is None:
            return None
        if not self.can_spend_for_unit(unit):
            return None
        cost = self.resurgence_cost_for_unit(unit)
        if cost is None:
            return None
        new_unit = self._clone_unit(unit)
        if new_unit is None:
            return None
        self.resurgence_points = int(self.resurgence_points or 0) - int(cost)
        self._prepare_unit_in_cult_ambush(new_unit, game=game)
        self._publish_update(game)
        return new_unit

    def unit_is_in_cult_ambush(self, unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "_cult_ambush", False)):
            return False
        try:
            return str(getattr(unit, "reserve_status", "deployed")) != "deployed"
        except Exception:
            return False

    def get_units_in_cult_ambush(self, *, game=None, only_arrivable: bool = False) -> list:
        units = []
        if self.army is None:
            return units
        for u in list(getattr(self.army, "units", []) or []):
            if not self.unit_is_in_cult_ambush(u):
                continue
            if only_arrivable and game is not None:
                try:
                    if not u.can_arrive_from_reserves(getattr(game, "turn", 0)):
                        continue
                except Exception:
                    continue
            units.append(u)
        return units

    def get_active_markers(self) -> list[CultAmbushMarker]:
        return [m for m in list(self.markers or []) if bool(getattr(m, "active", False))]

    def get_marker(self, marker_id: str) -> Optional[CultAmbushMarker]:
        key = str(marker_id or "").strip()
        if not key:
            return None
        for marker in list(self.markers or []):
            if str(getattr(marker, "marker_id", "") or "") != key:
                continue
            return marker
        return None

    @staticmethod
    def _normalize_ability_name(value: str) -> str:
        text = str(value or "").replace("\u2019", "'").strip().lower()
        return " ".join(text.split())

    def _model_has_named_ability(self, unit, model, ability_name: str) -> bool:
        target = self._normalize_ability_name(ability_name)
        if not target or unit is None or model is None:
            return False
        iter_entries = getattr(unit, "_iter_model_specific_ability_entries", None)
        if callable(iter_entries):
            for name, _desc in list(iter_entries(model) or []):
                if self._normalize_ability_name(name) == target:
                    return True
        return False

    def get_summon_the_cult_source_models(self, *, game=None) -> list:
        if self.army is None:
            return []
        models: list = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None or not self._unit_is_alive(unit) or not self._unit_on_battlefield(unit):
                continue
            for model in list(getattr(unit, "models", []) or []):
                if model is None:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not alive:
                    continue
                if not self._model_has_named_ability(unit, model, "Summon the Cult"):
                    continue
                model_id = str(get_entity_id(model) or "")
                if model_id and model_id in seen:
                    continue
                if model_id:
                    seen.add(model_id)
                models.append(model)
        models.sort(key=lambda model: str(get_entity_id(model) or ""))
        return models

    def get_cult_infiltration_sources(self) -> list[dict]:
        if self.army is None:
            return []
        sources: list[dict] = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not self._unit_is_alive(root) or not self._unit_on_battlefield(root):
                continue
            if not self._unit_has_named_ability(unit, "Cult Infiltration"):
                continue
            models = [model for model in list(getattr(unit, "models", []) or []) if getattr(model, "is_alive", True)]
            if not models:
                continue
            unit_id = str(get_entity_id(unit) or "")
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            sources.append(
                {
                    "root": root,
                    "unit": unit,
                    "model": models[0],
                }
            )
        sources.sort(
            key=lambda entry: (
                str(get_entity_id(entry.get("model")) or ""),
                str(get_entity_id(entry.get("unit")) or ""),
            )
        )
        return sources

    def marker_moved_this_turn(self, marker: CultAmbushMarker, *, game=None) -> bool:
        if marker is None or game is None:
            return False
        current_player = getattr(game, "get_current_player", lambda: None)()
        owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            return False
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        return (
            str(getattr(marker, "last_moved_turn_owner_id", "") or "") == owner_id
            and int(getattr(marker, "last_moved_turn", 0) or 0) == current_turn
        )

    def can_use_summon_the_cult(self, *, game=None) -> bool:
        if bool(self.summon_the_cult_used):
            return False
        return bool(self.get_summon_the_cult_source_models(game=game))

    def _marker_within_summon_the_cult_range(self, x: float, y: float, z: float, *, game=None) -> bool:
        source_models = self.get_summon_the_cult_source_models(game=game)
        if not source_models:
            return False
        point_base = Base(BaseType.CIRCULAR, 0.0)
        point_base.set_position(float(x), float(y), float(z))
        from ..utility.aura_utils import distance_between_bases_3d

        for model in list(source_models or []):
            model_base = getattr(model, "model_base", None)
            if model_base is None:
                continue
            if float(distance_between_bases_3d(model_base, point_base)) <= 12.0 + 1e-6:
                return True
        return False

    def validate_summon_the_cult_relocation(self, marker_id: str, point, *, game=None) -> tuple[bool, str]:
        marker = self.get_marker(marker_id)
        if marker is None or not bool(getattr(marker, "active", False)):
            return (False, "Cult Ambush marker is no longer active.")
        if bool(self.summon_the_cult_used):
            return (False, "Summon the Cult has already been used this battle.")
        if game is None:
            return (False, "Summon the Cult requires an active game.")
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return (False, "Summon the Cult requires a valid point.")
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return (False, "Summon the Cult point must be numeric.")
        if not self._marker_position_valid(game, x, y):
            return (False, "Summon the Cult marker must be more than 9\" horizontally from all enemy units and on the battlefield.")
        try:
            z = float(getattr(game.map, "get_height_at_point", lambda _x, _y: 0.0)(x, y))
        except Exception:
            z = float(getattr(marker, "z", 0.0) or 0.0)
        if not self._marker_within_summon_the_cult_range(x, y, z, game=game):
            return (False, "Summon the Cult marker must be within 12\" of a friendly model with Summon the Cult.")
        return (True, "")

    def _clear_pending_relocation(self, marker_ids: list[str] | tuple[str, ...] | None) -> None:
        for marker_id in list(marker_ids or []):
            marker = self.get_marker(marker_id)
            if marker is None:
                continue
            try:
                marker.pending_relocation = False
            except Exception:
                pass

    def apply_summon_the_cult_relocation(
        self,
        marker_id: str,
        point,
        *,
        threatened_marker_ids: list[str] | tuple[str, ...] | None = None,
        game=None,
    ) -> bool:
        valid, _reason = self.validate_summon_the_cult_relocation(marker_id, point, game=game)
        if not valid:
            return False
        marker = self.get_marker(marker_id)
        if marker is None:
            return False
        try:
            x = float(point[0])
            y = float(point[1])
            z = float(getattr(game.map, "get_height_at_point", lambda _x, _y: 0.0)(x, y))
        except Exception:
            return False
        marker.x = float(x)
        marker.y = float(y)
        marker.z = float(z)
        marker.active = True
        marker.pending_relocation = False
        self.summon_the_cult_used = True

        threatened_ids = [str(value or "").strip() for value in list(threatened_marker_ids or []) if str(value or "").strip()]
        self._clear_pending_relocation(threatened_ids)
        chosen_id = str(marker_id or "").strip()
        for threatened_id in threatened_ids:
            if threatened_id == chosen_id:
                continue
            other = self.get_marker(threatened_id)
            if other is None:
                continue
            self.remove_marker(other)
        self._publish_update(game)
        return True

    def skip_summon_the_cult_relocation(self, marker_ids: list[str] | tuple[str, ...] | None, *, game=None) -> None:
        threatened_ids = [str(value or "").strip() for value in list(marker_ids or []) if str(value or "").strip()]
        self._clear_pending_relocation(threatened_ids)
        for marker_id in threatened_ids:
            marker = self.get_marker(marker_id)
            if marker is None:
                continue
            self.remove_marker(marker)
        self._publish_update(game)

    def validate_evasive_vanguard_relocation(self, marker_id: str, point, *, game=None) -> tuple[bool, str]:
        marker = self.get_marker(marker_id)
        if marker is None or not bool(getattr(marker, "active", False)):
            return (False, "Cult Ambush marker is no longer active.")
        if game is None:
            return (False, "Evasive Vanguard requires an active game.")
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return (False, "Evasive Vanguard requires a valid point.")
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return (False, "Evasive Vanguard point must be numeric.")
        if not self._marker_position_valid(game, x, y):
            return (False, 'Evasive Vanguard marker must be more than 9" horizontally from all enemy units and on the battlefield.')
        return (True, "")

    def apply_evasive_vanguard_relocation(
        self,
        marker_id: str,
        point,
        *,
        threatened_marker_ids: list[str] | tuple[str, ...] | None = None,
        game=None,
    ) -> bool:
        valid, _reason = self.validate_evasive_vanguard_relocation(marker_id, point, game=game)
        if not valid:
            return False
        marker = self.get_marker(marker_id)
        if marker is None:
            return False
        try:
            x = float(point[0])
            y = float(point[1])
            z = float(getattr(game.map, "get_height_at_point", lambda _x, _y: 0.0)(x, y))
        except Exception:
            return False
        marker.x = float(x)
        marker.y = float(y)
        marker.z = float(z)
        marker.active = True
        marker.pending_relocation = False

        threatened_ids = [str(value or "").strip() for value in list(threatened_marker_ids or []) if str(value or "").strip()]
        self._clear_pending_relocation(threatened_ids)
        chosen_id = str(marker_id or "").strip()
        for threatened_id in threatened_ids:
            if threatened_id == chosen_id:
                continue
            other = self.get_marker(threatened_id)
            if other is None:
                continue
            self.remove_marker(other)
        self._publish_update(game)
        return True

    def skip_evasive_vanguard_relocation(self, marker_ids: list[str] | tuple[str, ...] | None, *, game=None) -> None:
        self.skip_summon_the_cult_relocation(marker_ids, game=game)

    def _marker_position_valid(self, game, x: float, y: float) -> bool:
        if not self._marker_position_on_battlefield(game, x, y):
            return False
        if game is None:
            return False
        try:
            enemy_units = list(game.get_enemy_units(getattr(self.army, "player", None)) or [])
        except Exception:
            enemy_units = []
        for unit in enemy_units:
            if not self._unit_on_battlefield(unit):
                continue
            for m in list(getattr(unit, "models", []) or []):
                if not getattr(m, "is_alive", True):
                    continue
                if horizontal_distance_point_to_model_base_2d(m, x, y) <= 9.0 + 1e-6:
                    return False
        return True

    def _marker_position_on_battlefield(self, game, x: float, y: float) -> bool:
        try:
            w = float(getattr(getattr(game, "battlefield", None), "width", 0.0))
            h = float(getattr(getattr(game, "battlefield", None), "height", 0.0))
        except Exception:
            return False
        if x < 0 or y < 0 or x > w or y > h:
            return False
        return True

    def validate_cult_infiltration_relocation(
        self,
        marker_id: str,
        point,
        *,
        source_unit_id: str = "",
        game=None,
    ) -> tuple[bool, str]:
        marker = self.get_marker(marker_id)
        if marker is None or not bool(getattr(marker, "active", False)):
            return (False, "Cult Ambush marker is no longer active.")
        if self.marker_moved_this_turn(marker, game=game):
            return (False, "Selected Cult Ambush marker has already been moved this turn.")
        if game is None:
            return (False, "Cult Infiltration requires an active game.")
        source_unit = None
        key = str(source_unit_id or "").strip()
        for entry in list(self.get_cult_infiltration_sources() or []):
            unit = entry.get("unit")
            if unit is None:
                continue
            if str(get_entity_id(unit) or "") != key:
                continue
            source_unit = unit
            break
        if source_unit is None:
            return (False, "Cult Infiltration source is unavailable.")
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return (False, "Cult Infiltration requires a valid point.")
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return (False, "Cult Infiltration point must be numeric.")
        if not self._marker_position_on_battlefield(game, x, y):
            return (False, "Cult Ambush marker must remain on the battlefield.")
        try:
            z = float(getattr(game.map, "get_height_at_point", lambda _x, _y: 0.0)(x, y))
        except Exception:
            z = float(getattr(marker, "z", 0.0) or 0.0)
        dx = float(x) - float(getattr(marker, "x", 0.0) or 0.0)
        dy = float(y) - float(getattr(marker, "y", 0.0) or 0.0)
        dz = float(z) - float(getattr(marker, "z", 0.0) or 0.0)
        distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
        if float(distance) > 6.0 + 1e-6:
            return (False, 'Cult Infiltration marker must be moved up to 6".')
        return (True, "")

    def apply_cult_infiltration_relocation(
        self,
        marker_id: str,
        point,
        *,
        source_unit_id: str = "",
        game=None,
    ) -> bool:
        valid, _reason = self.validate_cult_infiltration_relocation(
            marker_id,
            point,
            source_unit_id=source_unit_id,
            game=game,
        )
        if not valid:
            return False
        marker = self.get_marker(marker_id)
        if marker is None:
            return False
        try:
            x = float(point[0])
            y = float(point[1])
            z = float(getattr(game.map, "get_height_at_point", lambda _x, _y: 0.0)(x, y))
        except Exception:
            return False
        marker.x = float(x)
        marker.y = float(y)
        marker.z = float(z)
        marker.active = True
        marker.pending_relocation = False
        current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        marker.last_moved_turn_owner_id = str(getattr(current_player, "id", "") or "")
        try:
            marker.last_moved_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            marker.last_moved_turn = 0
        self._publish_update(game)
        return True

    def find_marker_position(self, game, attempts: int = 200) -> Optional[tuple[float, float]]:
        if game is None:
            return None
        try:
            w = float(getattr(getattr(game, "battlefield", None), "width", 0.0))
            h = float(getattr(getattr(game, "battlefield", None), "height", 0.0))
        except Exception:
            return None
        rng = resolve_rng(game)
        for _ in range(int(attempts or 0)):
            x = rng.uniform(0.5, max(0.5, w - 0.5))
            y = rng.uniform(0.5, max(0.5, h - 0.5))
            if self._marker_position_valid(game, x, y):
                return float(x), float(y)
        return None

    def place_marker_at(self, game, x: float, y: float) -> Optional[CultAmbushMarker]:
        if not self._army_has_rule():
            return None
        if game is None:
            return None
        if not self._marker_position_valid(game, float(x), float(y)):
            return None
        z = 0.0
        try:
            if hasattr(game, "map") and hasattr(game.map, "get_height_at_point"):
                z = float(game.map.get_height_at_point(float(x), float(y)))
        except Exception:
            z = 0.0
        marker = CultAmbushMarker(marker_id=str(uuid.uuid4()), x=float(x), y=float(y), z=float(z), active=True)
        self.markers.append(marker)
        self._publish_update(game)
        return marker

    def place_marker_random(self, game) -> Optional[CultAmbushMarker]:
        pos = self.find_marker_position(game)
        if not pos:
            return None
        return self.place_marker_at(game, pos[0], pos[1])

    def remove_marker(self, marker: CultAmbushMarker) -> None:
        if marker is None:
            return
        try:
            marker.active = False
            marker.pending_relocation = False
        except Exception:
            pass

    def on_enemy_unit_move_ended(self, enemy_unit, *, game=None) -> None:
        if enemy_unit is None:
            return
        if self.army is None:
            return
        try:
            if enemy_unit.get_parent_army() is self.army:
                return
        except Exception:
            pass
        try:
            if enemy_unit.has_any_keyword("AIRCRAFT"):
                return
        except Exception:
            pass
        if not self._unit_is_alive(enemy_unit):
            return
        if not self._unit_on_battlefield(enemy_unit):
            return
        threatened_markers: list[CultAmbushMarker] = []
        for marker in list(self.get_active_markers()):
            if bool(getattr(marker, "pending_relocation", False)):
                continue
            for m in list(getattr(enemy_unit, "models", []) or []):
                if not getattr(m, "is_alive", True):
                    continue
                if horizontal_distance_point_to_model_base_2d(m, marker.x, marker.y) <= 9.0 + 1e-6:
                    threatened_markers.append(marker)
                    break
        if not threatened_markers:
            return

        preserve_ids: set[str] = set()
        if game is not None:
            handler = getattr(game, "_handle_cult_ambush_threatened_markers", None)
            if callable(handler):
                try:
                    preserve_ids = {
                        str(value or "").strip()
                        for value in list(handler(self, enemy_unit, threatened_markers) or [])
                        if str(value or "").strip()
                    }
                except Exception:
                    preserve_ids = set()

        changed = False
        for marker in threatened_markers:
            marker_id = str(getattr(marker, "marker_id", "") or "")
            if marker_id in preserve_ids:
                try:
                    marker.pending_relocation = True
                except Exception:
                    pass
                changed = True
                continue
            self.remove_marker(marker)
            changed = True
        if changed:
            self._publish_update(game)

    def _placements_respect_enemy_distance(self, unit, placements, *, game=None) -> bool:
        if game is None:
            return True
        if unit is None or not placements:
            return False

        try:
            enemy_units = list(game.get_enemy_units(unit.get_parent_army().player) or [])
        except Exception:
            enemy_units = []
        enemy_models = []
        for eu in enemy_units:
            if not self._unit_on_battlefield(eu):
                continue
            for em in list(getattr(eu, "models", []) or []):
                if getattr(em, "is_alive", True):
                    enemy_models.append(em)

        min_enemy_distance = 9.0
        enemy_mode = self._cult_ambush_enemy_distance_mode(unit, game=game)
        if enemy_mode == "engagement_range":
            min_enemy_distance = float(ENGAGEMENT_RANGE_HORIZONTAL or 1.0) + 1e-6
        else:
            # Compute min enemy distance (Warp Rifts support).
            snapshot = [m.get_location() for m in getattr(unit, "models", []) or []]
            try:
                for model, pos in zip(getattr(unit, "models", []) or [], placements):
                    model.set_location(pos[0], pos[1], pos[2], pos[3])
                try:
                    min_enemy_distance = float(getattr(game, "_warp_rifts_min_distance", lambda _u: 9.0)(unit) or 9.0)
                except Exception:
                    min_enemy_distance = 9.0
            finally:
                for model, loc in zip(getattr(unit, "models", []) or [], snapshot):
                    if loc:
                        model.set_location(*loc)

        from ..utility.aura_utils import horizontal_distance_between_bases_2d
        for idx, (x, y, z, facing) in enumerate(placements):
            if idx >= len(getattr(unit, "models", []) or []):
                break
            base = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
            for em in enemy_models:
                if float(horizontal_distance_between_bases_2d(base, em.model_base)) < float(min_enemy_distance):
                    return False

        # Additional reserves denial checks (e.g., Omni-scramblers).
        try:
            if hasattr(game, "_reserves_denial_violated"):
                if bool(game._reserves_denial_violated(unit, placements)):
                    return False
        except Exception:
            pass
        return True

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except Exception:
                return unit
            if root is not None:
                return root
        return unit

    def _lying_in_wait_active(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if "lying_in_wait_cult_ambush_setup_max_distance" not in sr and "lying_in_wait_cult_ambush_enemy_distance_mode" not in sr:
            return False
        if game is None:
            return True
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        expected_phase = str(sr.get("lying_in_wait_expires_phase", "") or "").strip().upper()
        if expected_phase and phase_name and expected_phase != phase_name:
            return False
        turn = int(sr.get("lying_in_wait_turn", 0) or 0)
        current_turn = int(getattr(game, "turn", 0) or 0)
        if turn and current_turn and turn != current_turn:
            return False
        owner = str(sr.get("lying_in_wait_turn_owner", "") or "")
        if owner:
            current_player = getattr(game, "get_current_player", lambda: None)()
            current_owner = str(getattr(current_player, "id", "") or "")
            if current_owner and owner == current_owner:
                return False
        return True

    def _cult_ambush_setup_max_distance(self, unit, *, game=None) -> float:
        default_distance = 3.0
        if not self._lying_in_wait_active(unit, game=game):
            return default_distance
        root = self._unit_root(unit)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return default_distance
        try:
            value = float(sr.get("lying_in_wait_cult_ambush_setup_max_distance", default_distance) or default_distance)
        except Exception:
            value = default_distance
        if value <= 0:
            return default_distance
        return value

    def _cult_ambush_enemy_distance_mode(self, unit, *, game=None) -> str:
        if not self._lying_in_wait_active(unit, game=game):
            return ""
        root = self._unit_root(unit)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return ""
        return str(sr.get("lying_in_wait_cult_ambush_enemy_distance_mode", "") or "").strip().lower()

    def _cult_ambush_battlefield_edge_limit(self, unit) -> float:
        if not self._unit_has_named_ability(unit, "Outrider Gangs"):
            return 0.0
        return 9.0

    def _model_wholly_within_battlefield_edge_limit(
        self,
        model,
        x: float,
        y: float,
        *,
        game=None,
        edge_limit: float,
    ) -> bool:
        if model is None or game is None or edge_limit <= 0:
            return True
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        try:
            radius = float(model.model_base.get_longest_radius())
        except Exception:
            try:
                radius = float(model.model_base.get_radius())
            except Exception:
                radius = 0.0
        try:
            distances = (
                float(x),
                float(y),
                float(getattr(game_map, "width", 0.0) or 0.0) - float(x),
                float(getattr(game_map, "height", 0.0) or 0.0) - float(y),
            )
        except Exception:
            return False
        return float(min(distances)) + float(radius) <= float(edge_limit) + 1e-6

    def _placements_within_battlefield_edge_limit(self, unit, placements, *, game=None) -> bool:
        if unit is None or game is None:
            return False
        edge_limit = float(self._cult_ambush_battlefield_edge_limit(unit) or 0.0)
        if edge_limit <= 0:
            return True
        models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
        if len(models) > len(list(placements or [])):
            return False
        for model, pos in zip(models, list(placements or [])):
            if pos is None or len(pos) < 2:
                return False
            if not self._model_wholly_within_battlefield_edge_limit(
                model,
                float(pos[0]),
                float(pos[1]),
                game=game,
                edge_limit=edge_limit,
            ):
                return False
        return True

    def _find_cult_ambush_placements(self, unit, marker: CultAmbushMarker, *, game=None):
        if unit is None or marker is None or game is None:
            return None
        if not getattr(game, "map", None):
            return None
        models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
        if not models:
            return []
        setup_max_distance = self._cult_ambush_setup_max_distance(unit, game=game)

        marker_base = Base(BaseType.CIRCULAR, MARKER_RADIUS_INCHES)
        try:
            marker_base.set_position(marker.x, marker.y, marker.z)
        except Exception:
            pass

        first_model = models[0]
        try:
            mr = float(first_model.model_base.get_longest_radius())
        except Exception:
            try:
                mr = float(first_model.model_base.get_radius())
            except Exception:
                mr = 1.0
        touch_r = float(MARKER_RADIUS_INCHES) + float(mr)

        for deg in range(0, 360, 15):
            ang = math.radians(deg)
            x = marker.x + math.cos(ang) * touch_r
            y = marker.y + math.sin(ang) * touch_r
            try:
                z = float(game.map.get_height_at_point(x, y))
            except Exception:
                z = float(marker.z or 0.0)
            facing = 0.0

            try:
                if not game.map.is_within_boundary(first_model, destination=(x, y)):
                    continue
                if game.map.check_collision_with_terrain(first_model, destination=(x, y)):
                    continue
                if game.map.check_collision_with_other_friendly_units(first_model, destination=(x, y)):
                    continue
                if game.map.check_collision_with_other_enemy_units(first_model, destination=(x, y)):
                    continue
            except Exception:
                continue

            placed = [(x, y, z, facing)]
            ok = True
            for model in models[1:]:
                pos = unit._find_single_disembark_position(
                    model=model,
                    transport_base=marker_base,
                    game_map=game.map,
                    max_distance=float(setup_max_distance),
                    placed=placed,
                    require_not_in_engagement=False,
                )
                if pos is None:
                    ok = False
                    break
                placed.append(pos)
            if not ok:
                continue
            if not self._placements_respect_enemy_distance(unit, placed, game=game):
                continue
            if not self._placements_within_battlefield_edge_limit(unit, placed, game=game):
                continue
            return placed

        return None

    def deploy_unit_from_marker(self, unit, marker: CultAmbushMarker, *, game=None) -> bool:
        if unit is None or marker is None or game is None:
            return False
        if not bool(getattr(marker, "active", False)):
            return False
        if not self.unit_is_in_cult_ambush(unit):
            return False
        try:
            if not unit.can_arrive_from_reserves(getattr(game, "turn", 0)):
                return False
        except Exception:
            return False

        placements = self._find_cult_ambush_placements(unit, marker, game=game)
        if placements is None:
            return False

        for model, pos in zip(list(getattr(unit, "models", []) or []), placements):
            try:
                model.set_location(pos[0], pos[1], pos[2], pos[3])
            except Exception:
                pass

        try:
            unit.deployed = True
            unit.reserve_status = "deployed"
            unit.reserve_turn_deployed = int(getattr(game, "turn", 0) or 0)
            unit.arrived_from_reserves_this_turn = True
            unit.round_state.reinforced_this_round = True
            unit.round_state.remained_stationary_this_round = False
        except Exception:
            pass

        try:
            if unit not in game.map.units:
                game.map.units.append(unit)
        except Exception:
            pass
        try:
            root = self._unit_root(unit)
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                for key in (
                    "lying_in_wait_cult_ambush_setup_max_distance",
                    "lying_in_wait_cult_ambush_enemy_distance_mode",
                    "lying_in_wait_turn_owner",
                    "lying_in_wait_turn",
                    "lying_in_wait_expires_phase",
                    "lying_in_wait_source",
                ):
                    sr.pop(key, None)
                root.special_rules = sr
        except Exception:
            pass

        self.remove_marker(marker)
        self._publish_update(game)
        return True

    def handle_unit_destroyed(self, unit, *, game=None, player=None) -> Optional[object]:
        if unit is None:
            return None
        if not self.can_spend_for_unit(unit):
            return None
        if player is None:
            player = getattr(self.army, "player", None)
        new_unit = self.spend_resurgence_for_unit(unit, game=game)
        if new_unit is None:
            return None
        return new_unit

    def handle_reinforcements(self, *, game=None, player=None) -> list:
        if not self._army_has_rule():
            return []
        if game is None:
            return []
        if player is None:
            player = getattr(self.army, "player", None)
        markers = self.get_active_markers()
        if not markers:
            return []
        units = self.get_units_in_cult_ambush(game=game, only_arrivable=True)
        if not units:
            return []

        if not bool(getattr(game, "is_authoritative", True)):
            return []

        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return []

        unit_ids = [get_entity_id(u) for u in units]
        marker_ids = [str(m.marker_id) for m in markers]
        if not unit_ids or not marker_ids:
            return []

        marker_id = marker_ids[0]
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("ability", "")) == "cult_ambush_reinforcements" and str(ctx.get("marker_id", "")) == marker_id:
                    return []

        req_options = [DecisionOption.create("Skip (leave marker)", payload={"action": "skip"})]
        for unit in units:
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(unit)},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Cult Ambush unit.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "cult_ambush_reinforcements",
                "marker_id": marker_id,
                "remaining_marker_ids": list(marker_ids[1:]),
                "available_unit_ids": list(unit_ids),
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
        return []

    def _publish_update(self, game) -> None:
        try:
            es = getattr(game, "event_system", None) if game is not None else None
            if es is not None:
                es.publish("cult_ambush_updated", player=getattr(self.army, "player", None))
        except Exception:
            pass
