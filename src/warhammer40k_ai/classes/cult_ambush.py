from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_CULT_AMBUSH, army_has_ability_id
from ..utility.aura_utils import horizontal_distance_point_to_model_base_2d
from ..utility.model_base import Base, BaseType


MARKER_RADIUS_INCHES = 0.63  # 32mm diameter marker ≈ 1.26" across


@dataclass
class CultAmbushMarker:
    marker_id: str
    x: float
    y: float
    z: float = 0.0
    active: bool = True


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
        self.resurgence_points = int(self._tokens_for_battlefield(game))
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
            from .unit import Unit as UnitClass
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

    def _marker_position_valid(self, game, x: float, y: float) -> bool:
        try:
            w = float(getattr(getattr(game, "battlefield", None), "width", 0.0))
            h = float(getattr(getattr(game, "battlefield", None), "height", 0.0))
        except Exception:
            return False
        if x < 0 or y < 0 or x > w or y > h:
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

    def find_marker_position(self, game, attempts: int = 200) -> Optional[tuple[float, float]]:
        if game is None:
            return None
        try:
            w = float(getattr(getattr(game, "battlefield", None), "width", 0.0))
            h = float(getattr(getattr(game, "battlefield", None), "height", 0.0))
        except Exception:
            return None
        for _ in range(int(attempts or 0)):
            x = random.uniform(0.5, max(0.5, w - 0.5))
            y = random.uniform(0.5, max(0.5, h - 0.5))
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
        removed_any = False
        for marker in list(self.get_active_markers()):
            for m in list(getattr(enemy_unit, "models", []) or []):
                if not getattr(m, "is_alive", True):
                    continue
                if horizontal_distance_point_to_model_base_2d(m, marker.x, marker.y) <= 9.0 + 1e-6:
                    self.remove_marker(marker)
                    removed_any = True
                    break
        if removed_any:
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

        # Compute min enemy distance (Warp Rifts support).
        min_enemy_distance = 9.0
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

    def _find_cult_ambush_placements(self, unit, marker: CultAmbushMarker, *, game=None):
        if unit is None or marker is None or game is None:
            return None
        if not getattr(game, "map", None):
            return None
        models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
        if not models:
            return []

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
                if game.map.check_collision_with_obstacles(first_model, destination=(x, y)):
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
                    max_distance=3.0,
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
        should = False
        try:
            ctx = {
                "unit": unit,
                "cost": self.resurgence_cost_for_unit(unit),
                "points": int(self.resurgence_points or 0),
            }
            should = bool(player._should_use_optional_ability("CULT_AMBUSH", ctx))
        except Exception:
            should = False
        if not should:
            return None
        new_unit = self.spend_resurgence_for_unit(unit, game=game)
        if new_unit is None:
            return None
        # Auto-place marker for AI flows if possible.
        try:
            self.place_marker_random(game)
        except Exception:
            pass
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

        # Human players are handled by UI prompts (if subscribed).
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        es = getattr(game, "event_system", None)
        try:
            if is_human and es is not None:
                subs = getattr(es, "subscribers", {})
                if isinstance(subs, dict) and subs.get("cult_ambush_reinforcements_prompt"):
                    es.publish("cult_ambush_reinforcements_prompt", player=player, markers=list(markers), game=game)
                    return []
        except Exception:
            pass

        deployed = []
        available = list(units)
        for marker in list(markers):
            if not available:
                break
            unit = available.pop(0)
            if self.deploy_unit_from_marker(unit, marker, game=game):
                deployed.append(unit)
        return deployed

    def _publish_update(self, game) -> None:
        try:
            es = getattr(game, "event_system", None) if game is not None else None
            if es is not None:
                es.publish("cult_ambush_updated", player=getattr(self.army, "player", None))
        except Exception:
            pass
