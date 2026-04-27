from __future__ import annotations

"""Pathing-owned movement validation and collision helpers."""

from itertools import count
from math import sqrt
from typing import Mapping, Optional

from shapely import STRtree
from shapely.affinity import translate
from shapely.geometry import Point

from ..utility.constants import (
    BASE_CONTACT_EPSILON,
    CONSOLIDATE_DISTANCE,
    ENGAGEMENT_RANGE_HORIZONTAL,
    ENGAGEMENT_RANGE_VERTICAL,
    MM_TO_INCHES,
    PILE_IN_DISTANCE,
)
from ..utility.entity_ids import get_entity_id, maybe_entity_id
from ..battlefield.control_queries import control_region_centroid, control_region_shape
from ..battlefield.objective_sites import resolve_objective_id, resolve_objective_site
from .rules_profile import (
    build_movement_profile,
    get_freely_climbable_range,
    movement_type_allows_fly_over,
    movement_type_tag,
    unit_army_identity_key,
    unit_can_fly_over_big_models,
    unit_is_fly_move,
    units_share_army_identity,
)
from .surfaces import extract_ground_transit_obstacles
from .types import MovementProfile, MovementType


_terrain_cache: dict[tuple, list] = {}
_enemy_model_cache: dict[tuple, list] = {}
_enemy_model_big_cache: dict[tuple, list] = {}
_enemy_model_titanic_cache: dict[tuple, list] = {}
_enemy_aircraft_model_cache: dict[tuple, list] = {}
_enemy_engagement_buffer_cache: dict[tuple, list] = {}
_enemy_aircraft_engagement_buffer_cache: dict[tuple, list] = {}
_game_map_cache_key_counter = count(1)


def _require_game_map(game_map: object) -> None:
    if game_map is None:
        raise ValueError("Movement/path validation requires game_map; received None.")


def _convert_mm_to_inches(value: float) -> float:
    return round(float(value) / MM_TO_INCHES, 4)


def _game_map_cache_key(game_map: object) -> int:
    _require_game_map(game_map)
    cache_key = getattr(game_map, "_pathing_validation_cache_key", None)
    if isinstance(cache_key, int) and cache_key > 0:
        return cache_key
    next_key = int(next(_game_map_cache_key_counter))
    setattr(game_map, "_pathing_validation_cache_key", next_key)
    return next_key


def clear_validation_caches() -> None:
    _terrain_cache.clear()
    _enemy_model_cache.clear()
    _enemy_model_big_cache.clear()
    _enemy_model_titanic_cache.clear()
    _enemy_aircraft_model_cache.clear()
    _enemy_engagement_buffer_cache.clear()
    _enemy_aircraft_engagement_buffer_cache.clear()


def clear_validation_enemy_model_cache(game_map: object = None) -> None:
    if game_map is None:
        _enemy_model_cache.clear()
        _enemy_model_big_cache.clear()
        _enemy_model_titanic_cache.clear()
        _enemy_aircraft_model_cache.clear()
        _enemy_engagement_buffer_cache.clear()
        _enemy_aircraft_engagement_buffer_cache.clear()
        return

    if isinstance(game_map, int):
        cache_key = game_map
    else:
        cache_key = getattr(game_map, "_pathing_validation_cache_key", None)
        if not isinstance(cache_key, int) or cache_key <= 0:
            return
    for cache in (
        _enemy_model_cache,
        _enemy_model_big_cache,
        _enemy_model_titanic_cache,
        _enemy_aircraft_model_cache,
        _enemy_engagement_buffer_cache,
        _enemy_aircraft_engagement_buffer_cache,
    ):
        for key in [key for key in cache.keys() if key[0] == cache_key]:
            del cache[key]


def _unit_has_tau_crisis_faq_zero_pivot(unit: object) -> bool:
    if unit is None:
        return False
    datasheet_id = ""
    get_datasheet_id = getattr(unit, "get_datasheet_id", None)
    if callable(get_datasheet_id):
        try:
            datasheet_id = str(get_datasheet_id() or "").strip()
        except (AttributeError, TypeError, ValueError):
            datasheet_id = ""
    if datasheet_id in {"000000418", "000003699", "000003700", "000003701"}:
        return True
    name = str(getattr(unit, "name", "") or "").strip().lower()
    return bool(name.startswith("crisis ") and name.endswith(" battlesuits"))


def _unit_has_flying_base(unit: object) -> bool:
    if unit is None:
        return False
    for model in _unit_models_for_collision(unit):
        base = getattr(model, "model_base", None)
        if base is not None and bool(getattr(base, "is_flying_base", False)):
            return True
    return False


def get_pivot_cost(unit: object) -> float:
    if bool(getattr(unit, "is_aircraft", False)):
        return 0.0
    if _unit_has_tau_crisis_faq_zero_pivot(unit):
        return 0.0

    is_vehicle = bool(getattr(unit, "is_vehicle", False))
    is_monster = bool(getattr(unit, "is_monster", False))
    has_circular_base = bool(getattr(unit, "has_circular_base", False))
    if is_vehicle and has_circular_base:
        if float(getattr(unit, "base_size", 0.0) or 0.0) > _convert_mm_to_inches(32 / 2) and _unit_has_flying_base(unit):
            return 2.0
    if (is_vehicle or is_monster) and not has_circular_base:
        return 2.0
    if not has_circular_base:
        return 1.0
    return 0.0


def _unit_models_for_collision(unit: object) -> list:
    get_models = getattr(unit, "get_models_for_collision", None)
    if callable(get_models):
        return list(get_models() or [])
    return list(getattr(unit, "models", []) or [])


def _unit_is_alive(unit: object) -> bool:
    alive = getattr(unit, "is_alive", True)
    return bool(alive() if callable(alive) else alive)


def _model_is_alive(model: object) -> bool:
    alive = getattr(model, "is_alive", True)
    return bool(alive() if callable(alive) else alive)


def _unit_root_key(unit: object) -> str:
    get_root = getattr(unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else unit
    root_id = maybe_entity_id(root)
    if root_id:
        return str(root_id)
    return f"object:{id(root)}"


def _eligible_emplacement_platform_polygons(game_map: object, moving_model: object = None) -> dict[str, object]:
    if game_map is None or moving_model is None:
        return {}
    get_entries = getattr(game_map, "get_emplacement_platform_surface_entries", None)
    if not callable(get_entries):
        get_entries = getattr(game_map, "_iter_emplacement_platform_surface_entries", None)
    if not callable(get_entries):
        return {}

    polygons: dict[str, object] = {}
    for entry in tuple(get_entries(moving_model=moving_model, require_eligibility=True) or ()):
        source_unit = entry.get("source_unit")
        polygon = entry.get("polygon")
        source_unit_id = maybe_entity_id(source_unit)
        if source_unit_id is None or polygon is None:
            continue
        polygons[str(source_unit_id)] = polygon
    return polygons


def _query_spatial_index(tree: STRtree, query_geom) -> list:
    indices = tree.query(query_geom)
    if indices is None:
        return []
    try:
        if len(indices) == 0:
            return []
    except TypeError:
        return [tree.geometries[int(indices)]]
    return [tree.geometries[int(i)] for i in indices]


def _tyranids_overrun_normal_move_active(moving_unit: object) -> bool:
    sr = getattr(moving_unit, "special_rules", None)
    if not isinstance(sr, dict) or not bool(sr.get("tyranids_overrun_normal_move_active")):
        return False
    phase_name = ""
    current_turn = 0
    current_owner = ""
    army = None
    get_army = getattr(moving_unit, "get_parent_army", None)
    if callable(get_army):
        army = get_army()
    player = getattr(army, "player", None) if army is not None else None
    current_owner = str(getattr(player, "id", "") or "").strip()
    game = getattr(player, "game", None) if player is not None else None
    if game is not None:
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
    try:
        marked_turn = int(sr.get("tyranids_overrun_turn", 0) or 0)
    except (TypeError, ValueError):
        marked_turn = 0
    marked_owner = str(sr.get("tyranids_overrun_turn_owner", "") or "").strip()
    expires_phase = str(sr.get("tyranids_overrun_expires_phase", "") or "").strip().upper()
    if expires_phase and phase_name and expires_phase != phase_name:
        return False
    if marked_turn and current_turn and marked_turn != current_turn:
        return False
    if marked_owner and current_owner and marked_owner != current_owner:
        return False
    return True


def get_validation_rules(
    movement_type: object,
    target_unit: object = None,
    *,
    moving_unit: object = None,
    target_units: Optional[tuple[object, ...]] = None,
    movement_profile: object = None,
) -> dict[str, object]:
    if movement_profile is None:
        movement_profile = build_movement_profile(
            moving_unit,
            movement_type,
            target_unit=target_unit,
            target_units=target_units,
        )
    profile = movement_profile
    rules: dict[str, object] = {
        "prevent_friendly_overlap": True,
        "prevent_enemy_overlap": True,
        "apply_pivot_cost": profile.pivot_cost_mode != "none",
        "check_terrain_traversal": True,
        "can_move_through_enemy_models": bool(profile.can_move_through_enemy_models),
        "can_move_through_friendly_models": bool(profile.can_move_through_friendly_models),
        "can_move_through_terrain": bool(profile.can_move_through_terrain),
        "movement_profile": profile,
        "free_climb_height_inches": float(profile.free_climb_height_inches),
        "can_end_on_upper_surfaces": bool(profile.can_end_on_upper_surfaces),
        "cannot_end_within_engagement_range_of_aircraft": True,
    }

    if movement_type == MovementType.CHARGE:
        targets = list(target_units or ())
        if not targets and target_unit is not None:
            targets = [target_unit]
        rules.update(
            {
                "target_unit": targets[0] if targets else target_unit,
                "charge_target_units": targets,
                "charge_target_unit_ids": {get_entity_id(t) for t in targets if t is not None},
                "allow_engagement_range_movement": True,
                "allow_base_to_base_contact": True,
            }
        )
        if bool(getattr(moving_unit, "is_flying", False)) and any(
            bool(getattr(t, "is_aircraft", False)) for t in targets if t is not None
        ):
            rules["allow_end_in_engagement_range_of_aircraft"] = True
    elif movement_type == MovementType.FALL_BACK:
        rules.update(
            {
                "can_move_through_enemy_models": True,
                "cannot_end_in_engagement_range": True,
                "check_desperate_escape": True,
            }
        )
    elif movement_type == MovementType.SCOUT:
        rules.update({"min_distance_from_enemies": 9.0, "min_distance_from_deployment_zone": 9.0})
    elif movement_type in (MovementType.MOVE, MovementType.ADVANCE):
        rules["cannot_move_within_engagement_range"] = True
    elif movement_type == MovementType.PILE_IN:
        rules.update(
            {
                "must_end_closer_to_enemies": True,
                "prefer_base_contact": True,
                "max_distance_override": 3.0,
                "apply_pivot_cost": True,
                "distance_tolerance": 0.05,
            }
        )
    elif movement_type == MovementType.CONSOLIDATE:
        rules.update(
            {
                "must_end_closer_to_enemies_or_objectives": True,
                "prefer_base_contact": True,
                "max_distance_override": 3.0,
                "apply_pivot_cost": True,
                "distance_tolerance": 0.05,
            }
        )
        if _tyranids_overrun_normal_move_active(moving_unit):
            normal_move_distance = 6.0
            sr = getattr(moving_unit, "special_rules", None)
            if isinstance(sr, dict):
                try:
                    normal_move_distance = float(sr.get("tyranids_overrun_normal_move_distance", 6.0) or 6.0)
                except (TypeError, ValueError):
                    normal_move_distance = 6.0
            rules["max_distance_override"] = max(float(rules["max_distance_override"]), normal_move_distance)
            rules["must_end_closer_to_enemies_or_objectives"] = False
            rules["prefer_base_contact"] = False
            rules["cannot_move_within_engagement_range"] = True
            rules["cannot_end_in_engagement_range"] = True
    elif movement_type in (
        MovementType.BLOOD_SURGE,
        MovementType.BRAZEN_FURY,
        MovementType.HORDE_MOVE,
        MovementType.SURGE_MOVE,
        MovementType.BLISTERING_ASSAULT,
        MovementType.BESTIAL_RAGE,
    ):
        rules.update(
            {
                "allow_engagement_range_movement": True,
                "must_end_as_close_as_possible_to_closest_enemy_unit": True,
                "closest_enemy_unit_reason": str(getattr(movement_type, "value", movement_type)),
                "distance_tolerance": 0.05,
            }
        )

    if bool(getattr(moving_unit, "is_flying", False)) and movement_type_allows_fly_over(movement_type):
        rules["can_move_through_enemy_models"] = True
        if movement_type in (MovementType.MOVE, MovementType.ADVANCE):
            rules["cannot_move_within_engagement_range"] = False
            rules["cannot_end_in_engagement_range"] = True

    if bool(getattr(profile, "can_move_through_enemy_models", False)):
        rules["can_move_through_enemy_models"] = True
    if bool(getattr(profile, "can_move_through_friendly_models", False)):
        rules["can_move_through_friendly_models"] = True
    if bool(getattr(profile, "can_move_through_terrain", False)):
        rules["can_move_through_terrain"] = True
    if rules.get("can_move_through_enemy_models") or rules.get("can_move_through_friendly_models"):
        rules["can_move_through_models"] = True

    move_tag = movement_type_tag(movement_type)
    sr = getattr(moving_unit, "special_rules", None)
    if isinstance(sr, dict):
        if move_tag == "fall_back" and bool(sr.get("bearer_unit_auto_pass_desperate_escape")):
            rules["check_desperate_escape"] = False
        phase_move_types = {str(v) for v in list(sr.get("bearer_unit_phase_move_types", []) or []) if v}
        if move_tag and move_tag in phase_move_types:
            rules["can_move_through_enemy_models"] = True
            rules["can_move_through_friendly_models"] = True
            rules["can_move_through_terrain"] = True
            if not bool(getattr(profile, "block_titanic_models", False)) and not bool(
                getattr(profile, "block_monster_vehicle_models", False)
            ):
                rules["ignore_enemy_models_blocking"] = True
            if movement_type in (MovementType.MOVE, MovementType.ADVANCE, MovementType.FALL_BACK):
                rules["cannot_move_within_engagement_range"] = False
                rules["cannot_end_in_engagement_range"] = True

    return rules


def build_collision_trees(
    moving_unit: object,
    movement_type: object,
    game_map: object,
    *,
    moving_model: object = None,
    moved_models_in_unit: Optional[set[object]] = None,
    max_distance: Optional[float] = None,
    target_position: Optional[tuple[float, float, float]] = None,
    movement_profile: object = None,
) -> dict[str, object]:
    _require_game_map(game_map)
    if moved_models_in_unit is None:
        moved_models_in_unit = set()
    if movement_profile is None:
        movement_profile = build_movement_profile(moving_unit, movement_type)
    emplacement_platform_polygons = _eligible_emplacement_platform_polygons(game_map, moving_model)

    if moving_model is not None:
        center_pos = (moving_model.model_base.x, moving_model.model_base.y)
        model_radius = float(moving_model.model_base.get_radius())
    else:
        alive_models = [model for model in _unit_models_for_collision(moving_unit) if _model_is_alive(model)]
        if alive_models:
            center_pos = (alive_models[0].model_base.x, alive_models[0].model_base.y)
            model_radius = float(alive_models[0].model_base.get_radius())
        else:
            center_pos = (0.0, 0.0)
            model_radius = 1.0

    if max_distance is None:
        max_distance = 12.0
        safety_buffer = 36.0
    else:
        safety_buffer = max(4.0, model_radius + 2.0)
    if movement_type in (
        MovementType.MOVE,
        MovementType.ADVANCE,
        MovementType.CHARGE,
        MovementType.BLOOD_SURGE,
        MovementType.BRAZEN_FURY,
        MovementType.HORDE_MOVE,
        MovementType.SURGE_MOVE,
        MovementType.BLISTERING_ASSAULT,
        MovementType.BESTIAL_RAGE,
    ):
        search_radius = float(max_distance) + model_radius + ENGAGEMENT_RANGE_HORIZONTAL + safety_buffer
    else:
        search_radius = float(max_distance) + safety_buffer

    def is_within_search_area(shape_or_pos) -> bool:
        if hasattr(shape_or_pos, "centroid"):
            shape_center = (shape_or_pos.centroid.x, shape_or_pos.centroid.y)
        elif hasattr(shape_or_pos, "x") and hasattr(shape_or_pos, "y"):
            shape_center = (shape_or_pos.x, shape_or_pos.y)
        else:
            shape_center = (shape_or_pos[0], shape_or_pos[1])
        distance_2d = sqrt((shape_center[0] - center_pos[0]) ** 2 + (shape_center[1] - center_pos[1]) ** 2)
        return distance_2d <= search_radius

    unit_keywords = tuple(sorted(getattr(moving_unit, "keywords", []) or ()))
    climbable_range = get_freely_climbable_range(moving_unit, movement_type)
    map_cache_key = _game_map_cache_key(game_map)
    terrain_cache_key = (map_cache_key, unit_keywords, climbable_range, movement_type)
    if terrain_cache_key in _terrain_cache:
        all_blocking_terrain = _terrain_cache[terrain_cache_key]
    else:
        all_blocking_terrain = list(extract_ground_transit_obstacles(game_map, movement_profile))
        _terrain_cache[terrain_cache_key] = all_blocking_terrain
    blocking_terrain = [poly for poly in all_blocking_terrain if is_within_search_area(poly)]

    enemy_cache_key = (map_cache_key, unit_army_identity_key(moving_unit))
    if enemy_cache_key in _enemy_model_cache:
        all_enemy_shapes = _enemy_model_cache[enemy_cache_key]
        all_enemy_big_shapes = _enemy_model_big_cache.get(enemy_cache_key, [])
        all_enemy_titanic_shapes = _enemy_model_titanic_cache.get(enemy_cache_key, [])
        all_enemy_aircraft_shapes = _enemy_aircraft_model_cache.get(enemy_cache_key, [])
    else:
        all_enemy_shapes = []
        all_enemy_big_shapes = []
        all_enemy_titanic_shapes = []
        all_enemy_aircraft_shapes = []
        for unit in list(getattr(game_map, "units", []) or []):
            if not _unit_is_alive(unit) or not bool(getattr(unit, "deployed", True)):
                continue
            if units_share_army_identity(unit, moving_unit):
                continue
            is_aircraft = bool(getattr(unit, "is_aircraft", False))
            is_titanic = bool(getattr(unit, "is_titanic", False))
            is_big = bool(
                getattr(unit, "is_monster", False)
                or getattr(unit, "is_vehicle", False)
                or is_titanic
            )
            for model in _unit_models_for_collision(unit):
                if not _model_is_alive(model):
                    continue
                shape = model.model_base.get_base_shape()
                if is_aircraft:
                    all_enemy_aircraft_shapes.append(shape)
                else:
                    all_enemy_shapes.append(shape)
                    if is_big:
                        all_enemy_big_shapes.append(shape)
                    if is_titanic:
                        all_enemy_titanic_shapes.append(shape)
        _enemy_model_cache[enemy_cache_key] = all_enemy_shapes
        _enemy_model_big_cache[enemy_cache_key] = all_enemy_big_shapes
        _enemy_model_titanic_cache[enemy_cache_key] = all_enemy_titanic_shapes
        _enemy_aircraft_model_cache[enemy_cache_key] = all_enemy_aircraft_shapes

    enemy_models = [shape for shape in all_enemy_shapes if is_within_search_area(shape)]
    enemy_aircraft_models = [shape for shape in all_enemy_aircraft_shapes if is_within_search_area(shape)]
    blocking_enemy_models = []
    if movement_type == MovementType.CAREEN or bool(getattr(movement_profile, "block_monster_vehicle_models", False)):
        blocking_enemy_models = [shape for shape in all_enemy_big_shapes if is_within_search_area(shape)]
    elif bool(getattr(movement_profile, "block_titanic_models", False)):
        blocking_enemy_models = [shape for shape in all_enemy_titanic_shapes if is_within_search_area(shape)]
    elif unit_is_fly_move(moving_unit, movement_type) and not unit_can_fly_over_big_models(moving_unit, movement_type):
        blocking_enemy_models = [shape for shape in all_enemy_big_shapes if is_within_search_area(shape)]

    allow_move_over_friendly_big = bool(
        getattr(movement_profile, "terrain_transition_rules", {}).get("can_move_over_friendly_monster_vehicle", False)
    )
    friendly_models = []
    friendly_models_passable = []
    for unit in list(getattr(game_map, "units", []) or []):
        if not _unit_is_alive(unit) or not bool(getattr(unit, "deployed", True)):
            continue
        if not units_share_army_identity(unit, moving_unit):
            continue
        unit_is_big = bool(allow_move_over_friendly_big and (getattr(unit, "is_monster", False) or getattr(unit, "is_vehicle", False)))
        for model_index, model in enumerate(_unit_models_for_collision(unit)):
            if not _model_is_alive(model):
                continue
            if moving_model is not None and model is moving_model:
                continue
            model_pos = (model.model_base.x, model.model_base.y)
            if not is_within_search_area(model_pos):
                continue
            if unit is moving_unit:
                moved = model in moved_models_in_unit or model_index in moved_models_in_unit
                if not moved:
                    continue
            model_shape = model.model_base.get_base_shape()
            platform_polygon = emplacement_platform_polygons.get(_unit_root_key(unit))
            if platform_polygon is not None:
                adjusted_shape = model_shape.difference(platform_polygon)
                if adjusted_shape.is_empty:
                    continue
                model_shape = adjusted_shape
            if unit_is_big:
                friendly_models_passable.append(model_shape)
            else:
                friendly_models.append(model_shape)

    trees = {
        "terrain": STRtree(blocking_terrain) if blocking_terrain else None,
        "friendly_models": STRtree(friendly_models) if friendly_models else None,
        "friendly_models_passable": STRtree(friendly_models_passable) if friendly_models_passable else None,
        "enemy_models": STRtree(enemy_models) if enemy_models else None,
        "enemy_aircraft_models": STRtree(enemy_aircraft_models) if enemy_aircraft_models else None,
    }
    if blocking_enemy_models:
        trees["enemy_models_blocking"] = STRtree(blocking_enemy_models)

    overrun_normal_move = bool(movement_type == MovementType.CONSOLIDATE and _tyranids_overrun_normal_move_active(moving_unit))
    if movement_type in (MovementType.MOVE, MovementType.ADVANCE) or overrun_normal_move:
        if all_enemy_shapes:
            if enemy_cache_key in _enemy_engagement_buffer_cache:
                all_buffered = _enemy_engagement_buffer_cache[enemy_cache_key]
            else:
                all_buffered = [shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL) for shape in all_enemy_shapes]
                _enemy_engagement_buffer_cache[enemy_cache_key] = all_buffered
            buffered_enemies = [shape for shape in all_buffered if is_within_search_area(shape)]
            if buffered_enemies:
                trees["engagement_buffer"] = STRtree(buffered_enemies)
    elif movement_type == MovementType.SCOUT and enemy_models:
        trees["engagement_buffer"] = STRtree([shape.buffer(9.0) for shape in enemy_models])

    if all_enemy_aircraft_shapes:
        if enemy_cache_key in _enemy_aircraft_engagement_buffer_cache:
            all_aircraft_buffered = _enemy_aircraft_engagement_buffer_cache[enemy_cache_key]
        else:
            all_aircraft_buffered = [shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL) for shape in all_enemy_aircraft_shapes]
            _enemy_aircraft_engagement_buffer_cache[enemy_cache_key] = all_aircraft_buffered
        buffered_aircraft = [shape for shape in all_aircraft_buffered if is_within_search_area(shape)]
        if buffered_aircraft:
            trees["engagement_buffer_aircraft"] = STRtree(buffered_aircraft)
    return trees


def _temp_base_at(model: object, position: tuple[float, float, float], *, facing: float | None = None):
    from ..utility.model_base import clone_base

    temp_base = clone_base(model.model_base)
    temp_base.set_position(position[0], position[1], position[2])
    if facing is None:
        facing = float(getattr(model.model_base, "facing", 0.0) or 0.0)
    temp_base.set_facing(float(facing))
    return temp_base


def _edge_distance_to_enemy(temp_base, enemy_model: object) -> tuple[float, float]:
    from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

    return (
        float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base)),
        float(vertical_distance_between_bases(temp_base, enemy_model.model_base)),
    )


def _distance_between_bases_3d(base_a: object, base_b: object) -> float:
    from ..utility.aura_utils import distance_between_bases_3d

    return float(distance_between_bases_3d(base_a, base_b))


def _model_location(model: object) -> tuple[float, float, float] | None:
    get_location = getattr(model, "get_location", None)
    if callable(get_location):
        location = tuple(get_location() or ())
        if len(location) >= 3:
            return (float(location[0]), float(location[1]), float(location[2]))
    base = getattr(model, "model_base", None)
    if base is None:
        return None
    return (
        float(getattr(base, "x", 0.0) or 0.0),
        float(getattr(base, "y", 0.0) or 0.0),
        float(getattr(base, "z", 0.0) or 0.0),
    )


def _iter_enemy_models(game_map: object, moving_unit: object) -> list:
    enemies = []
    for unit in list(getattr(game_map, "units", []) or []):
        if units_share_army_identity(unit, moving_unit) or not _unit_is_alive(unit) or not bool(getattr(unit, "deployed", True)):
            continue
        for enemy_model in _unit_models_for_collision(unit):
            if _model_is_alive(enemy_model):
                enemies.append(enemy_model)
    return enemies


def _enemy_models_with_current_distance(game_map: object, moving_unit: object, current_base: object) -> list[tuple[object, float]]:
    return [
        (enemy_model, _distance_between_bases_3d(current_base, enemy_model.model_base))
        for enemy_model in _iter_enemy_models(game_map, moving_unit)
    ]


def _new_base_in_engagement(enemy_models: list[object], new_base: object) -> bool:
    for enemy_model in enemy_models:
        horizontal, vertical = _edge_distance_to_enemy(new_base, enemy_model)
        if horizontal <= ENGAGEMENT_RANGE_HORIZONTAL and vertical <= ENGAGEMENT_RANGE_VERTICAL:
            return True
    return False


def _objective_closer_and_in_range(
    *,
    game_map: object,
    current_base: object,
    new_base: object,
    validation_rules: Mapping[str, object],
) -> bool:
    objectives = list(getattr(game_map, "objectives", []) or [])
    allowed_objective_ids = {
        str(value or "").strip()
        for value in list(validation_rules.get("consolidate_allowed_objective_ids", []) or [])
        if str(value or "").strip()
    }
    if allowed_objective_ids:
        objectives = [
            objective
            for objective in objectives
            if str(resolve_objective_id(objective) or "").strip() in allowed_objective_ids
        ]
    if not objectives:
        return False

    current_point = Point(float(current_base.x or 0.0), float(current_base.y or 0.0))
    closest_entry = None
    closest_distance = None
    for objective in objectives:
        site = resolve_objective_site(objective)
        if site is None or bool(getattr(site, "removed", False)):
            continue
        control_region = getattr(site, "control_region", None)
        shape = control_region_shape(control_region, game_state=getattr(game_map, "game", None)) if control_region is not None else None
        centroid = (
            control_region_centroid(control_region, game_state=getattr(game_map, "game", None))
            if control_region is not None
            else (
                float(getattr(site, "x", 0.0) or 0.0),
                float(getattr(site, "y", 0.0) or 0.0),
                float(getattr(site, "z", 0.0) or 0.0),
            )
        )
        if shape is not None:
            current_distance = float(shape.distance(current_point))
        else:
            dx = float(current_base.x or 0.0) - float(centroid[0] if len(centroid) > 0 else 0.0)
            dy = float(current_base.y or 0.0) - float(centroid[1] if len(centroid) > 1 else 0.0)
            current_distance = sqrt((dx * dx) + (dy * dy))
        if closest_distance is None or current_distance < closest_distance:
            closest_distance = current_distance
            closest_entry = (site, shape, centroid)

    if closest_entry is None or closest_distance is None:
        return False

    site, objective_shape, centroid = closest_entry
    new_shape_getter = getattr(new_base, "get_base_shape", None)
    new_shape = new_shape_getter() if callable(new_shape_getter) else None
    if objective_shape is not None and new_shape is not None:
        within = bool(new_shape.intersects(objective_shape))
        new_distance = float(objective_shape.distance(Point(float(new_base.x or 0.0), float(new_base.y or 0.0))))
    else:
        ox = float(centroid[0] if len(centroid) > 0 else 0.0)
        oy = float(centroid[1] if len(centroid) > 1 else 0.0)
        radius = float(getattr(resolve_objective_site(site), "control_radius", 3.0) or 0.0)
        dx = float(new_base.x or 0.0) - ox
        dy = float(new_base.y or 0.0) - oy
        new_distance = sqrt((dx * dx) + (dy * dy))
        get_radius = getattr(new_base, "get_longest_radius", None)
        base_radius = float(get_radius()) if callable(get_radius) else float(getattr(new_base, "radius", 0.0) or 0.0)
        within = new_distance <= (radius + base_radius + 1e-6)
    return bool(within and new_distance < (float(closest_distance) - 1e-6))


def _validate_pile_in_final_position(
    *,
    model: object,
    current_base: object,
    new_base: object,
    validation_rules: Mapping[str, object],
    game_map: object,
) -> dict[str, object]:
    moving_unit = getattr(model, "parent_unit", None)
    max_relevant_distance = ENGAGEMENT_RANGE_HORIZONTAL + float(validation_rules.get("max_distance_override", PILE_IN_DISTANCE) or PILE_IN_DISTANCE)
    enemy_distances = [
        (enemy_model, distance)
        for enemy_model, distance in _enemy_models_with_current_distance(game_map, moving_unit, current_base)
        if distance <= max_relevant_distance
    ]
    if not enemy_distances:
        return {"valid": False, "reason": "No enemy models within pile-in range for validation"}

    closest_enemy, closest_distance = min(enemy_distances, key=lambda entry: entry[1])
    new_distance = _distance_between_bases_3d(new_base, closest_enemy.model_base)
    tolerance = float(validation_rules.get("distance_tolerance", 0.0) or 0.0)
    if new_distance >= (float(closest_distance) - tolerance):
        return {
            "valid": False,
            "reason": f'Pile-in must end closer to closest enemy ({getattr(closest_enemy, "name", "enemy")}): {new_distance:.2f}" >= {closest_distance:.2f}"',
        }
    if bool(validation_rules.get("prefer_base_contact", False)):
        pile_in_distance = float(validation_rules.get("max_distance_override", PILE_IN_DISTANCE) or PILE_IN_DISTANCE)
        if float(closest_distance) <= pile_in_distance and new_distance > BASE_CONTACT_EPSILON:
            return {
                "valid": False,
                "reason": f'Pile-in must end in base contact with closest enemy ({getattr(closest_enemy, "name", "enemy")}) when possible',
            }
    return {"valid": True, "reason": "Valid final position"}


def _validate_consolidate_final_position(
    *,
    model: object,
    current_base: object,
    new_base: object,
    validation_rules: Mapping[str, object],
    game_map: object,
) -> dict[str, object]:
    moving_unit = getattr(model, "parent_unit", None)
    max_distance = float(validation_rules.get("max_distance_override", CONSOLIDATE_DISTANCE) or CONSOLIDATE_DISTANCE)
    max_relevant_distance = ENGAGEMENT_RANGE_HORIZONTAL + max_distance
    requires_engagement = bool(validation_rules.get("consolidate_requires_engagement", False))
    ignore_closest_enemy = bool(validation_rules.get("consolidate_ignore_closest_enemy_requirement", False))

    all_enemy_distances = _enemy_models_with_current_distance(game_map, moving_unit, current_base)
    enemy_distances = [
        (enemy_model, distance)
        for enemy_model, distance in all_enemy_distances
        if distance <= max_relevant_distance
    ]
    enemy_models = [enemy_model for enemy_model, _distance in enemy_distances]
    in_engagement = _new_base_in_engagement(enemy_models, new_base)

    if not enemy_distances:
        if (not requires_engagement) and _objective_closer_and_in_range(
            game_map=game_map,
            current_base=current_base,
            new_base=new_base,
            validation_rules=validation_rules,
        ):
            return {"valid": True, "reason": "Valid final position (objective)"}
        return {
            "valid": False,
            "reason": "Consolidate must end closer to an eligible objective marker and within range of it",
        }

    closest_enemy, closest_distance = min(enemy_distances, key=lambda entry: entry[1])
    engagement_possible = float(closest_distance) <= max_relevant_distance
    if requires_engagement and not in_engagement:
        return {"valid": False, "reason": "Consolidate must end within engagement range of an enemy unit"}
    if engagement_possible and not in_engagement:
        return {
            "valid": False,
            "reason": "Consolidate must end within engagement range of an enemy unit when possible",
        }

    new_distance = _distance_between_bases_3d(new_base, closest_enemy.model_base)
    tolerance = float(validation_rules.get("distance_tolerance", 0.0) or 0.0)
    if (not ignore_closest_enemy) and new_distance >= (float(closest_distance) - tolerance):
        return {
            "valid": False,
            "reason": f'Consolidate must end closer to closest enemy ({getattr(closest_enemy, "name", "enemy")}): {new_distance:.2f}" >= {closest_distance:.2f}"',
        }
    if bool(validation_rules.get("prefer_base_contact", False)) and not ignore_closest_enemy:
        if float(closest_distance) <= max_distance and new_distance > BASE_CONTACT_EPSILON:
            return {
                "valid": False,
                "reason": f'Consolidate must end in base contact with closest enemy ({getattr(closest_enemy, "name", "enemy")}) when possible',
            }
    return {"valid": True, "reason": "Valid final position"}


def _validate_final_position(
    model: object,
    position: tuple[float, float, float],
    validation_rules: Mapping[str, object],
    game_map: object,
    *,
    facing: float | None = None,
) -> dict[str, object]:
    _require_game_map(game_map)
    temp_base = _temp_base_at(model, position, facing=facing)
    moving_unit = getattr(model, "parent_unit", None)

    if validation_rules.get("must_end_in_engagement_range", False):
        target_unit = validation_rules.get("target_unit")
        if not target_unit:
            return {"valid": False, "reason": "No target unit specified for charge"}
        in_range = False
        for enemy_model in _unit_models_for_collision(target_unit):
            if not _model_is_alive(enemy_model):
                continue
            horizontal, vertical = _edge_distance_to_enemy(temp_base, enemy_model)
            if horizontal <= ENGAGEMENT_RANGE_HORIZONTAL and vertical <= ENGAGEMENT_RANGE_VERTICAL:
                in_range = True
                break
        if not in_range:
            return {"valid": False, "reason": "Charge must end within engagement range of target unit"}

    if validation_rules.get("cannot_end_in_engagement_range", False):
        for enemy_model in _iter_enemy_models(game_map, moving_unit):
            horizontal, vertical = _edge_distance_to_enemy(temp_base, enemy_model)
            if horizontal < ENGAGEMENT_RANGE_HORIZONTAL and vertical <= ENGAGEMENT_RANGE_VERTICAL:
                return {"valid": False, "reason": "Move cannot end within engagement range"}

    if validation_rules.get("must_end_closer_to_enemies", False) or validation_rules.get(
        "must_end_closer_to_enemies_or_objectives", False
    ):
        current_position = _model_location(model)
        if current_position is None:
            return {"valid": False, "reason": "Cannot determine current model position"}
        current_base = _temp_base_at(model, current_position)
        if validation_rules.get("must_end_closer_to_enemies", False):
            return _validate_pile_in_final_position(
                model=model,
                current_base=current_base,
                new_base=temp_base,
                validation_rules=validation_rules,
                game_map=game_map,
            )
        return _validate_consolidate_final_position(
            model=model,
            current_base=current_base,
            new_base=temp_base,
            validation_rules=validation_rules,
            game_map=game_map,
        )

    if validation_rules.get("min_distance_from_enemies", 0) > 0:
        min_distance = float(validation_rules["min_distance_from_enemies"])
        from ..utility.aura_utils import distance_between_bases_3d

        for enemy_model in _iter_enemy_models(game_map, moving_unit):
            distance = float(distance_between_bases_3d(temp_base, enemy_model.model_base))
            if distance < min_distance:
                return {"valid": False, "reason": f'Scout movement must end {min_distance}" from enemies'}

    return {"valid": True, "reason": "Valid final position"}


def is_position_valid_unified_detailed(
    position: tuple[float, float, float],
    model: object,
    collision_trees: Mapping[str, object],
    validation_rules: Mapping[str, object],
    game_map: object = None,
    *,
    is_final_position: bool = True,
    facing: float | None = None,
) -> dict[str, object]:
    _require_game_map(game_map)
    px = float(position[0])
    py = float(position[1])
    pz = float(position[2])
    validation_facing = float(facing) if facing is not None else float(getattr(model.model_base, "facing", 0.0) or 0.0)
    test_shape = model.model_base.get_base_shape_at(px, py, validation_facing)

    bounds = test_shape.bounds
    width = getattr(game_map, "width", None)
    height = getattr(game_map, "height", None)
    if width is not None and height is not None:
        if bounds[0] < 0.0 or bounds[1] < 0.0 or bounds[2] > float(width) or bounds[3] > float(height):
            return {"valid": False, "reason": "Position outside battlefield boundaries"}
    else:
        boundary = getattr(game_map, "boundary", None)
        if boundary is not None:
            if not boundary.contains(test_shape) and not boundary.covers(test_shape):
                return {"valid": False, "reason": "Position outside battlefield boundaries"}
        else:
            is_within_boundary = getattr(game_map, "is_within_boundary", None)
            if callable(is_within_boundary) and not bool(is_within_boundary(model, (px, py))):
                return {"valid": False, "reason": "Position outside battlefield boundaries"}

    allow_through_terrain = bool(validation_rules.get("can_move_through_terrain", False))
    terrain_tree = collision_trees.get("terrain") if collision_trees else None
    if terrain_tree is not None and not (allow_through_terrain and not is_final_position):
        for hit_shape in _query_spatial_index(terrain_tree, test_shape):
            if test_shape.intersects(hit_shape):
                return {"valid": False, "reason": "Position blocked by terrain"}

    allow_through_friendly = validation_rules.get(
        "can_move_through_friendly_models",
        validation_rules.get("can_move_through_models", False),
    )
    allow_through_enemy = validation_rules.get(
        "can_move_through_enemy_models",
        validation_rules.get("can_move_through_models", False),
    )

    def blocked_by_tree(tree: object) -> bool:
        if tree is None:
            return False
        for hit_shape in _query_spatial_index(tree, test_shape):
            if test_shape.intersects(hit_shape):
                return True
        return False

    if validation_rules.get("prevent_friendly_overlap", True):
        if ((not allow_through_friendly) or is_final_position) and blocked_by_tree(collision_trees.get("friendly_models")):
            return {"valid": False, "reason": "Position blocked by friendly models"}
        if is_final_position and blocked_by_tree(collision_trees.get("friendly_models_passable")):
            return {"valid": False, "reason": "Position blocked by friendly models"}

    ignore_enemy_models_blocking = bool(validation_rules.get("ignore_enemy_models_blocking", False))
    if not is_final_position and not ignore_enemy_models_blocking and blocked_by_tree(collision_trees.get("enemy_models_blocking")):
        return {"valid": False, "reason": "Position blocked by enemy models"}

    if validation_rules.get("prevent_enemy_overlap", True):
        if ((not allow_through_enemy) or is_final_position) and blocked_by_tree(collision_trees.get("enemy_models")):
            if allow_through_enemy and is_final_position and validation_rules.get("cannot_end_in_engagement_range", False):
                return {"valid": False, "reason": "Position within engagement range of enemy models"}
            return {"valid": False, "reason": "Position blocked by enemy models"}
        if is_final_position and blocked_by_tree(collision_trees.get("enemy_aircraft_models")):
            return {"valid": False, "reason": "Position blocked by enemy aircraft"}

    if validation_rules.get("cannot_move_within_engagement_range", False):
        engagement_tree = collision_trees.get("engagement_buffer") if collision_trees else None
        if engagement_tree is not None:
            for hit in _query_spatial_index(engagement_tree, test_shape):
                if test_shape.intersects(hit):
                    return {"valid": False, "reason": "Position within engagement range of enemy models"}

    if (
        validation_rules.get("cannot_end_within_engagement_range_of_aircraft", False)
        and is_final_position
        and not validation_rules.get("allow_end_in_engagement_range_of_aircraft", False)
    ):
        aircraft_tree = collision_trees.get("engagement_buffer_aircraft") if collision_trees else None
        if aircraft_tree is not None:
            for hit in _query_spatial_index(aircraft_tree, test_shape):
                if test_shape.intersects(hit):
                    return {"valid": False, "reason": "Position within engagement range of enemy aircraft"}

    if is_final_position:
        final_validation = _validate_final_position(
            model,
            (px, py, pz),
            validation_rules,
            game_map,
            facing=validation_facing,
        )
        if not final_validation.get("valid", False):
            return final_validation

    return {"valid": True, "reason": "Position is valid"}


__all__ = [
    "build_collision_trees",
    "get_pivot_cost",
    "get_validation_rules",
    "is_position_valid_unified_detailed",
]
