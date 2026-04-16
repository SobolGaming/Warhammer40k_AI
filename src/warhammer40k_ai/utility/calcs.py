from math import sqrt, atan2, pi, cos, sin, acos
from typing import Tuple, List, Optional
import heapq
from itertools import count
import numpy as np
from ..utility.constants import (
    MM_TO_INCHES,
    ENGAGEMENT_RANGE_VERTICAL,
    RUINS_FLOOR_HEIGHT,
    RUINS_FLOOR_THICKNESS,
)
from shapely.geometry import LineString, Point, Polygon, box
from shapely.affinity import translate, rotate
from shapely.ops import unary_union
from shapely import STRtree

from ..battlefield.control_queries import control_region_centroid, control_region_shape
from ..battlefield.objective_sites import resolve_objective_id, resolve_objective_site
from ..utility.entity_ids import get_entity_id, maybe_entity_id
from ..pathing.sweep import swept_footprint
from ..pathing.types import MovementProfile, MovementType, Pose
from ..pathing.rules_profile import (
    build_movement_profile,
    can_breach_ruins_walls as _can_breach_ruins_walls,
    get_freely_climbable_range,
    movement_type_allows_fly_over as _movement_type_allows_fly_over,
    movement_type_tag as _movement_type_tag,
    ruins_wall_traversal_allowed as _ruins_wall_traversal_allowed,
    super_heavy_walker_active_for_move as _super_heavy_walker_active_for_move,
    unit_army_identity_key as _unit_army_identity_key,
    unit_can_fly_over_big_models as _unit_can_fly_over_big_models,
    unit_ignores_vertical_distance as _unit_ignores_vertical_distance,
    unit_is_fly_move as _unit_is_fly_move,
    units_share_army_identity as _units_share_army_identity,
)
from ..pathing.surfaces import extract_ground_transit_obstacles

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from warhammer40k_ai.battlefield.map import TerrainFeature
    from warhammer40k_ai.units.unit import Unit, MovementAction
    from warhammer40k_ai.units.model import Model
    from warhammer40k_ai.battlefield.map import Map

import logging
logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

# Import existing constants
from .constants import ENGAGEMENT_RANGE_HORIZONTAL

# Global caches for collision detection
_terrain_cache = {}  # Cache for terrain blocking polygons by (game_map_id, unit_keywords, movement_type)
_enemy_model_cache = {}  # Cache for non-aircraft enemy model shapes by (game_map_id, army_identity)
_enemy_model_big_cache = {}  # Cache for non-aircraft MONSTER/VEHICLE shapes by (game_map_id, army_identity)
_enemy_aircraft_model_cache = {}  # Cache for enemy AIRCRAFT model shapes by (game_map_id, army_identity)
_enemy_engagement_buffer_cache = {}  # Cache for buffered non-aircraft enemy shapes by (game_map_id, army_identity)
_enemy_aircraft_engagement_buffer_cache = {}  # Cache for buffered aircraft shapes by (game_map_id, army_identity)
_game_map_cache_key_counter = count(1)


def game_map_cache_key(game_map: object) -> int:
    """Return a stable per-map cache token that cannot collide via Python id reuse."""
    cache_key = getattr(game_map, "_collision_cache_key", None)
    if isinstance(cache_key, int) and cache_key > 0:
        return cache_key
    next_key = int(next(_game_map_cache_key_counter))
    setattr(game_map, "_collision_cache_key", next_key)
    return next_key


def clear_collision_caches():
    """Clear all collision detection caches. Call when models die or game state changes significantly."""
    global _terrain_cache, _enemy_model_cache, _enemy_model_big_cache
    global _enemy_aircraft_model_cache, _enemy_engagement_buffer_cache, _enemy_aircraft_engagement_buffer_cache
    _terrain_cache.clear()
    _enemy_model_cache.clear()
    _enemy_model_big_cache.clear()
    _enemy_aircraft_model_cache.clear()
    _enemy_engagement_buffer_cache.clear()
    _enemy_aircraft_engagement_buffer_cache.clear()
    logger.debug("Cleared collision detection caches")


def clear_enemy_model_cache(game_map_id: object = None):
    """Clear enemy model cache for a specific game map/cache token or all maps."""
    global _enemy_model_cache, _enemy_model_big_cache, _enemy_aircraft_model_cache
    global _enemy_engagement_buffer_cache, _enemy_aircraft_engagement_buffer_cache
    if game_map_id is None:
        _enemy_model_cache.clear()
        _enemy_model_big_cache.clear()
        _enemy_aircraft_model_cache.clear()
        _enemy_engagement_buffer_cache.clear()
        _enemy_aircraft_engagement_buffer_cache.clear()
        logger.debug("Cleared all enemy model caches")
    else:
        cache_key = int(game_map_id) if isinstance(game_map_id, int) else game_map_cache_key(game_map_id)
        keys_to_remove = [key for key in _enemy_model_cache.keys() if key[0] == cache_key]
        for key in keys_to_remove:
            del _enemy_model_cache[key]
        keys_to_remove = [key for key in _enemy_model_big_cache.keys() if key[0] == cache_key]
        for key in keys_to_remove:
            del _enemy_model_big_cache[key]
        keys_to_remove = [key for key in _enemy_aircraft_model_cache.keys() if key[0] == cache_key]
        for key in keys_to_remove:
            del _enemy_aircraft_model_cache[key]
        keys_to_remove = [key for key in _enemy_engagement_buffer_cache.keys() if key[0] == cache_key]
        for key in keys_to_remove:
            del _enemy_engagement_buffer_cache[key]
        keys_to_remove = [key for key in _enemy_aircraft_engagement_buffer_cache.keys() if key[0] == cache_key]
        for key in keys_to_remove:
            del _enemy_aircraft_engagement_buffer_cache[key]
        logger.debug("Cleared enemy model cache for game map %s", cache_key)


def _eligible_emplacement_platform_polygons(game_map: 'Map', moving_model: 'Model' = None) -> dict[str, object]:
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

# Convert mm (as in base size of models) to inches
def convert_mm_to_inches(value: float) -> float:
    return round(value / MM_TO_INCHES, 4)

# Determine the distance of a 3D position delta
def get_dist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between to X,Y points
def get_angle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)

def angle_difference(angle1: float, angle2: float) -> float:
    """
    Calculate the smallest difference between two angles in radians.
    The result is in the range [-pi, pi].
    """
    diff = (angle2 - angle1 + pi) % (2 * pi) - pi
    return diff

def _is_position_on_terrain(game_map: 'Map', position: Tuple[float, float, float]) -> bool:
    if game_map is None:
        return False
    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    if not terrain_features:
        return False
    try:
        point = Point(float(position[0]), float(position[1]))
    except (TypeError, ValueError, IndexError):
        return False
    for terrain_feature in terrain_features:
        footprint = getattr(terrain_feature, "footprint", None)
        if footprint is None:
            continue
        if footprint.contains(point):
            return True
    return False

def _fly_use_diagonal(unit: 'Unit', movement_type, game_map: 'Map',
                      start_pos: Tuple[float, float, float], end_pos: Tuple[float, float, float]) -> bool:
    if not _unit_is_fly_move(unit, movement_type):
        return False
    if game_map is not None:
        if _is_position_on_terrain(game_map, start_pos) or _is_position_on_terrain(game_map, end_pos):
            return True
    try:
        return abs(float(end_pos[2]) - float(start_pos[2])) > 1e-6
    except (TypeError, ValueError, IndexError):
        return False

def movement_segment_cost(start: Tuple[float, float, float], end: Tuple[float, float, float],
                          unit: 'Unit', movement_type=None) -> float:
    """Return movement cost for a single segment using rules-aware vertical handling."""
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    horiz = sqrt(dx * dx + dy * dy)

    if _unit_ignores_vertical_distance(unit, movement_type):
        return horiz
    if _unit_is_fly_move(unit, movement_type):
        return horiz

    dz = 0.0
    try:
        dz = abs(float(end[2]) - float(start[2]))
    except (TypeError, ValueError, IndexError):
        dz = 0.0
    threshold = get_freely_climbable_range(unit, movement_type)
    vertical = dz if dz > threshold else 0.0
    return horiz + vertical

def measure_path_distance(path: List[Tuple[float, float, float]], unit: 'Unit',
                          movement_type=None, game_map: 'Map' = None) -> float:
    """Measure total path distance with vertical rules and FLY/Flip Belt handling."""
    if not path or len(path) < 2:
        return 0.0

    def _pos(p) -> Tuple[float, float, float]:
        try:
            return (float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0)
        except (TypeError, ValueError, IndexError):
            return (0.0, 0.0, 0.0)

    positions = [_pos(p) for p in path]
    horiz_total = 0.0
    for i in range(1, len(positions)):
        dx = positions[i][0] - positions[i - 1][0]
        dy = positions[i][1] - positions[i - 1][1]
        horiz_total += sqrt(dx * dx + dy * dy)

    if _unit_ignores_vertical_distance(unit, movement_type):
        return horiz_total

    if _unit_is_fly_move(unit, movement_type):
        if _fly_use_diagonal(unit, movement_type, game_map, positions[0], positions[-1]):
            dz_total = positions[-1][2] - positions[0][2]
            return sqrt(horiz_total * horiz_total + dz_total * dz_total)
        return horiz_total

    threshold = get_freely_climbable_range(unit, movement_type)
    vertical_total = 0.0
    for i in range(1, len(positions)):
        dz = abs(positions[i][2] - positions[i - 1][2])
        if dz > threshold:
            vertical_total += dz
    return horiz_total + vertical_total

def measure_direct_distance(start: Tuple[float, float, float], end: Tuple[float, float, float],
                            unit: 'Unit', movement_type=None, game_map: 'Map' = None) -> float:
    """Measure direct (best-case) distance between two points with vertical rules applied."""
    return measure_path_distance([start, end], unit, movement_type, game_map)

def can_traverse_freely(unit: 'Unit', terrain_feature: 'TerrainFeature') -> bool:
    """Check if a unit can freely traverse over terrain without vertical movement cost.

    This function determines if terrain should be ignored for pathfinding purposes.
    """
    # Import at runtime to avoid circular import
    from warhammer40k_ai.battlefield.map import TerrainType, RuinsTerrain

    terrain_type = terrain_feature.terrain_type

    # RUINS have special traversal rules
    if terrain_type == TerrainType.RUINS and isinstance(terrain_feature, RuinsTerrain):
        if _can_breach_ruins_walls(unit):
            return True
        try:
            if bool(getattr(unit, "is_flying", False)):
                return True
        except Exception:
            pass
        threshold = get_freely_climbable_range(unit)
        for wall in list(getattr(terrain_feature, "walls", []) or []):
            try:
                z0 = float(wall.get("z_bottom", 0.0) or 0.0)
                z1 = float(wall.get("z_top", 0.0) or 0.0)
                if (z1 - z0) > float(threshold):
                    return False
            except Exception as exc:
                raise RuntimeError("RUINS wall metadata missing") from exc
        return True

    # Flying units can traverse any other terrain freely
    if unit.is_flying:
        return True
    try:
        if unit is not None and hasattr(unit, "has_super_heavy_walker") and unit.has_super_heavy_walker():
            return True
    except Exception:
        pass

    # For other terrain types, check height-based traversal rules
    # Most terrain <=2" height can be traversed freely (Super-heavy Walker extends to 4")
    max_height = getattr(terrain_feature, 'height', 0.0)
    if max_height <= get_freely_climbable_range(unit):
        return True

    # All other terrain types >2" can be traversed but require vertical movement cost
    return False

def is_terrain_impassable(unit: 'Unit', terrain_feature: 'TerrainFeature',
                          movement_type: Optional['MovementType'] = None) -> bool:
    """Check if terrain is completely impassable for a unit.

    This determines if terrain should be added to blocking collision trees.
    """
    # Import at runtime to avoid circular import
    from warhammer40k_ai.battlefield.map import TerrainType, RuinsTerrain

    terrain_type = terrain_feature.terrain_type

    # Only RUINS walls are truly impassable for certain unit types
    if terrain_type == TerrainType.RUINS and isinstance(terrain_feature, RuinsTerrain):
        fly_move = _unit_is_fly_move(unit, movement_type) if movement_type is not None else bool(getattr(unit, "is_flying", False))
        if fly_move:
            return False
        can_traverse_walls = _ruins_wall_traversal_allowed(unit, movement_type)

        if not can_traverse_walls:
            # Core movement rule: terrain features <= 2" tall can be moved over "as if not there".
            # Apply this to RUINS wall segments as well (e.g., rubble/low walls).
            threshold = get_freely_climbable_range(unit, movement_type)
            for wall in list(getattr(terrain_feature, "walls", []) or []):
                try:
                    z0 = float(wall.get("z_bottom", 0.0) or 0.0)
                    z1 = float(wall.get("z_top", 0.0) or 0.0)
                    if (z1 - z0) > float(threshold):
                        return True
                except Exception as exc:
                    raise RuntimeError("RUINS wall metadata missing") from exc
            return False
        return False

    # Flying units can pass through non-RUINS terrain
    if unit.is_flying:
        return False
    if _super_heavy_walker_active_for_move(unit, movement_type):
        return False

    # Check terrain-specific traversal rules
    traversal_rules = getattr(terrain_feature, 'traversal_rules', {})

    # BARRICADES can block vehicles if very tall
    if terrain_type == TerrainType.BARRICADE_AND_FUEL_PIPES:
        if traversal_rules.get('blocks_vehicles', False) and 'Vehicle' in getattr(unit, 'keywords', []):
            return True

    # All other terrain types are passable (may require vertical cost)
    return False

def get_terrain_blocking_polygons(unit: 'Unit', terrain_feature: 'TerrainFeature',
                                  movement_type: Optional['MovementType'] = None) -> List:
    """Get list of polygons that block movement for a specific unit.

    Args:
        unit: The unit attempting to move
        terrain_feature: The terrain feature

    Returns:
        List of Polygon objects that block the unit's movement
    """
    # Import at runtime to avoid circular import
    from warhammer40k_ai.battlefield.map import TerrainType, RuinsTerrain

    blocking_polygons = []
    terrain_type = terrain_feature.terrain_type

    # RUINS: only walls block movement for non-Infantry/Beast units
    if terrain_type == TerrainType.RUINS and isinstance(terrain_feature, RuinsTerrain):
        fly_move = _unit_is_fly_move(unit, movement_type) if movement_type is not None else bool(getattr(unit, "is_flying", False))
        if fly_move:
            return []
        can_traverse_walls = _ruins_wall_traversal_allowed(unit, movement_type)

        if not can_traverse_walls:
            # Add wall polygons as blocking ONLY if wall segment height exceeds the climbable threshold.
            threshold = get_freely_climbable_range(unit, movement_type)
            for wall in list(getattr(terrain_feature, "walls", []) or []):
                try:
                    z0 = float(wall.get("z_bottom", 0.0) or 0.0)
                    z1 = float(wall.get("z_top", 0.0) or 0.0)
                    if (z1 - z0) <= float(threshold):
                        continue
                    poly = wall.get("polygon", None)
                    if poly is not None:
                        blocking_polygons.append(poly)
                except Exception as exc:
                    raise RuntimeError("RUINS wall polygon metadata missing") from exc

    # For other terrain types, check if they're impassable
    else:
        if unit.is_flying:
            return []
        if is_terrain_impassable(unit, terrain_feature, movement_type=movement_type):
            # Add the main footprint as blocking
            blocking_polygons.append(terrain_feature.footprint)

    return blocking_polygons

def _unit_has_flying_base(unit: 'Unit') -> bool:
    models = getattr(unit, "models", None) or []
    if not models:
        return False
    base = getattr(models[0], "model_base", None)
    return bool(getattr(base, "is_flying_base", False))


def _unit_has_tau_crisis_faq_zero_pivot(unit: 'Unit') -> bool:
    if unit is None:
        return False
    datasheet_id = ""
    try:
        datasheet_id = str(unit.get_datasheet_id() or "").strip()
    except Exception:
        datasheet_id = ""
    if datasheet_id in {"000000418", "000003699", "000003700", "000003701"}:
        return True
    try:
        name = str(getattr(unit, "name", "") or "").strip().lower()
    except Exception:
        return False
    return bool(name.startswith("crisis ") and name.endswith(" battlesuits"))


def get_pivot_cost(unit: 'Unit') -> float:
    """
    Calculate the pivot cost for a unit based on its characteristics.
    """
    if bool(getattr(unit, "is_aircraft", False)):
        return 0
    if _unit_has_tau_crisis_faq_zero_pivot(unit):
        return 0

    is_vehicle = bool(getattr(unit, "is_vehicle", False))
    is_monster = bool(getattr(unit, "is_monster", False))

    if is_vehicle and unit.has_circular_base:
        if unit.base_size > convert_mm_to_inches(32 / 2) and _unit_has_flying_base(unit):
            return 2
    if (is_vehicle or is_monster) and not unit.has_circular_base:
        return 2
    if not unit.has_circular_base:
        return 1
    return 0

def get_movement_cost(model: 'Model', point_a: Tuple[float, float], point_b: Tuple[float, float], terrain_features: List['TerrainFeature']) -> float:
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]
    dz = 0  # Initialize vertical distance

    # Create a line representing the movement path
    #print(f"A: {point_a}, B: {point_b}")
    movement_line = LineString([point_a, point_b])

    # Find terrain features that intersect the movement path
    intersecting_terrain = []
    for terrain_feature in terrain_features:
        if movement_line.intersects(terrain_feature.footprint):
            intersecting_terrain.append(terrain_feature)

    # Determine the maximum terrain height along the path that requires vertical movement
    max_terrain_height = 0
    threshold = get_freely_climbable_range(model.parent_unit)
    for terrain_feature in intersecting_terrain:
        # Only consider terrain that is not impassable
        if not is_terrain_impassable(model.parent_unit, terrain_feature):
            # Get terrain height
            terrain_height = getattr(terrain_feature, 'height', 0.0)
            # If terrain is > threshold height, it requires vertical movement cost
            if terrain_height > threshold:
                if terrain_height > max_terrain_height:
                    max_terrain_height = terrain_height

    # Set vertical distance based on the highest terrain that requires climbing
    dz = max_terrain_height if max_terrain_height > threshold else 0

    # For units with 'Fly', they pay vertical movement cost but can traverse over obstacles
    if model.parent_unit.is_flying:
        pass  # They can fly over obstacles but must pay vertical cost
    else:
        # For non-flying units, check if they can climb over the obstacle
        if dz > model.movement:
            return float('inf')  # Cannot traverse over the obstacle

    # Calculate total movement cost including vertical distance
    total_distance = get_dist(dx, dy, dz)
    return total_distance

def heuristic(a, b):
    """Calculate the heuristic (estimated distance) between two points."""
    return get_dist(a[0] - b[0], a[1] - b[1], a[2] - b[2])

def heuristic_2d(a, b):
    """Calculate the heuristic (estimated distance) between two 2D points."""
    return ((a[0] - b[0])**2 + (a[1] - b[1])**2)**0.5

def check_friendly_ending_collision(model: 'Model', end_pos: Tuple[float, float, float], game_map: 'Map') -> bool:
    """
    Check if ending position would collide with friendly models.
    
    Args:
        model: The model to check
        end_pos: The ending position (x, y, z)
        game_map: The game map
        
    Returns:
        bool: True if ending position collides with friendly models
    """
    # Create temporary base at ending position
    temp_base = model.model_base.__class__(model.model_base.base_type, model.model_base.radius)
    temp_base.set_position(end_pos[0], end_pos[1], end_pos[2])
    temp_base.set_facing(model.model_base.facing)
    
    # Check against friendly units (excluding own unit)
    friendly_units = game_map.get_friendly_units(model.parent_unit)
    for friendly_unit in friendly_units:
        if friendly_unit == model.parent_unit or not friendly_unit.is_alive() or not friendly_unit.deployed:
            continue
            
        for friendly_model in friendly_unit.models:
            if not friendly_model.is_alive:
                continue
                
            if temp_base.collides_with(friendly_model.model_base):
                return True
                
    return False

# =============================================================================
# UNIFIED PATHFINDING SYSTEM
# =============================================================================

def build_collision_trees(moving_unit: 'Unit', movement_type: MovementType, game_map: 'Map',
                         moving_model: 'Model' = None, moved_models_in_unit: set = None,
                         max_distance: float = None, target_position: tuple = None,
                         movement_profile: Optional[MovementProfile] = None) -> dict:
    """
    Build STRTrees for collision detection based on movement type and unit capabilities.

    PERFORMANCE OPTIMIZATION: Only includes objects within movement range + safety buffer.

    For individual model movement, pass moving_model and moved_models_in_unit to properly
    handle same-unit collision detection.

    Args:
        moving_unit: The unit that is moving
        movement_type: Type of movement being performed
        game_map: The game map containing all objects
        moving_model: Specific model being moved (for individual model movement)
        moved_models_in_unit: Set of model indices already moved in this unit
        max_distance: Maximum movement distance for spatial filtering

    Returns:
        Dict containing STRTrees for different collision types
    """
    if moved_models_in_unit is None:
        moved_models_in_unit = set()
    if movement_profile is None:
        movement_profile = build_movement_profile(moving_unit, movement_type)
    emplacement_platform_polygons = _eligible_emplacement_platform_polygons(game_map, moving_model)

    def _unit_models_for_collision(u):
        try:
            return u.get_models_for_collision()
        except Exception:
            return u.models

    def _unit_root_key(u) -> str:
        get_root = getattr(u, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else u
        root_id = maybe_entity_id(root)
        if root_id:
            return str(root_id)
        return f"object:{id(root)}"

    def _is_moved(model_index: int, model_obj: 'Model') -> bool:
        """Support both old (indices) and new (model objects) moved_models_in_unit inputs."""
        try:
            if model_obj in moved_models_in_unit:
                return True
        except Exception:
            pass
        try:
            if model_index in moved_models_in_unit:
                return True
        except Exception:
            pass
        return False

    # Get the moving model's position for spatial filtering
    if moving_model:
        center_pos = (moving_model.model_base.x, moving_model.model_base.y)
        model_radius = moving_model.model_base.get_radius()
    else:
        # Use first alive model as reference
        alive_models = [m for m in _unit_models_for_collision(moving_unit) if m.is_alive]
        if alive_models:
            center_pos = (alive_models[0].model_base.x, alive_models[0].model_base.y)
            model_radius = alive_models[0].model_base.get_radius()
        else:
            center_pos = (0, 0)
            model_radius = 1.0

    # Calculate search radius: movement distance + model radius + safety buffer
    if max_distance is None:
        # When max_distance is not specified (e.g., in tests or validation),
        # use a very large search radius to avoid filtering out important objects
        max_distance = 12.0  # Default maximum movement
        safety_buffer = 36.0  # Large buffer for test/validation scenarios
    else:
        # For actual pathfinding, use optimized spatial filtering
        safety_buffer = max(4.0, model_radius + 2.0)  # At least 4" safety buffer

    # CRITICAL FIX: For engagement range validation, we need to account for models
    # that might be near the destination, not just the starting position.
    # Formula: max_movement_distance + model_base_radius + engagement_range + buffer
    if movement_type in [
        MovementType.MOVE,
        MovementType.ADVANCE,
        MovementType.CHARGE,
        MovementType.BLOOD_SURGE,
        MovementType.BRAZEN_FURY,
        MovementType.HORDE_MOVE,
        MovementType.BLISTERING_ASSAULT,
        MovementType.BESTIAL_RAGE,
    ]:
        # Calculate the actual maximum possible movement distance for this movement type
        actual_max_movement = max_distance
        if movement_type == MovementType.ADVANCE:
            # ADVANCE can add up to 6" additional movement (max D6 roll)
            actual_max_movement = max_distance + 6.0
        elif movement_type == MovementType.CHARGE:
            # CHARGE uses 2D6, so max additional 12" (though this is rare)
            # But charge distance is already calculated, so max_distance should be correct
            pass
        
        # Search radius = starting position + max possible movement + model radius + engagement range + buffer
        search_radius = actual_max_movement + model_radius + ENGAGEMENT_RANGE_HORIZONTAL + safety_buffer
    else:
        search_radius = max_distance + safety_buffer

    allow_move_over_friendly_big = bool(
        movement_profile.terrain_transition_rules.get("can_move_over_friendly_monster_vehicle", False)
    )

    def is_within_search_area(shape_or_pos):
        """Check if a shape or position is within the search area (2D distance only)."""
        try:
            if hasattr(shape_or_pos, 'centroid'):
                # It's a shape - use 2D centroid
                shape_center = (shape_or_pos.centroid.x, shape_or_pos.centroid.y)
            elif hasattr(shape_or_pos, 'x') and hasattr(shape_or_pos, 'y'):
                # It's a position object - use 2D coordinates
                shape_center = (shape_or_pos.x, shape_or_pos.y)
            else:
                # It's a tuple/list - use first two coordinates for 2D distance
                shape_center = (shape_or_pos[0], shape_or_pos[1])

            # Calculate 2D distance only (ignore Z coordinate for spatial filtering)
            # This ensures models on different floors are still considered for collision
            distance_2d = ((shape_center[0] - center_pos[0])**2 + (shape_center[1] - center_pos[1])**2)**0.5
            return distance_2d <= search_radius
        except Exception:
            # If we can't determine position, include it to be safe
            return True

    # Get terrain blocking polygons with caching and spatial filtering
    unit_keywords = tuple(sorted(moving_unit.keywords)) if hasattr(moving_unit, 'keywords') else ()
    climbable_range = get_freely_climbable_range(moving_unit, movement_type)
    map_cache_key = game_map_cache_key(game_map)
    terrain_cache_key = (map_cache_key, unit_keywords, climbable_range, movement_type)
    if terrain_cache_key in _terrain_cache:
        all_blocking_terrain = _terrain_cache[terrain_cache_key]
    else:
        all_blocking_terrain = list(
            extract_ground_transit_obstacles(
                game_map,
                movement_profile,
            )
        )
        _terrain_cache[terrain_cache_key] = all_blocking_terrain

    # Apply spatial filtering to terrain for this move
    blocking_terrain = [poly for poly in all_blocking_terrain if is_within_search_area(poly)]

    # Get enemy models with caching and spatial filtering (split aircraft vs non-aircraft)
    enemy_cache_key = (map_cache_key, _unit_army_identity_key(moving_unit))
    if enemy_cache_key in _enemy_model_cache:
        all_enemy_shapes = _enemy_model_cache[enemy_cache_key]
        all_enemy_big_shapes = _enemy_model_big_cache.get(enemy_cache_key, [])
        all_enemy_aircraft_shapes = _enemy_aircraft_model_cache.get(enemy_cache_key, [])
    else:
        all_enemy_shapes = []
        all_enemy_big_shapes = []
        all_enemy_aircraft_shapes = []
        for unit in game_map.units:
            if not unit.is_alive() or not unit.deployed:
                continue
            if _units_share_army_identity(unit, moving_unit):
                continue
            try:
                is_aircraft = bool(getattr(unit, "is_aircraft", False))
            except Exception:
                is_aircraft = False
            try:
                is_big = bool(getattr(unit, "is_monster", False) or getattr(unit, "is_vehicle", False) or getattr(unit, "is_titanic", False))
            except Exception:
                is_big = False
            for model in _unit_models_for_collision(unit):
                if model.is_alive:
                    shape = model.model_base.get_base_shape()
                    if is_aircraft:
                        all_enemy_aircraft_shapes.append(shape)
                    else:
                        all_enemy_shapes.append(shape)
                        if is_big:
                            all_enemy_big_shapes.append(shape)
        _enemy_model_cache[enemy_cache_key] = all_enemy_shapes
        _enemy_model_big_cache[enemy_cache_key] = all_enemy_big_shapes
        _enemy_aircraft_model_cache[enemy_cache_key] = all_enemy_aircraft_shapes

    enemy_models = [shape for shape in all_enemy_shapes if is_within_search_area(shape)]
    enemy_aircraft_models = [shape for shape in all_enemy_aircraft_shapes if is_within_search_area(shape)]

    # FLY over enemy models: block only enemy MONSTER/VEHICLE models for non-MONSTER/VEHICLE flyers.
    # Aircraft are ignored for this blocking rule.
    blocking_enemy_models = []
    if movement_type == MovementType.CAREEN:
        blocking_enemy_models = [shape for shape in all_enemy_big_shapes if is_within_search_area(shape)]
    elif _unit_is_fly_move(moving_unit, movement_type) and not _unit_can_fly_over_big_models(moving_unit, movement_type):
        blocking_enemy_models = [shape for shape in all_enemy_big_shapes if is_within_search_area(shape)]

    # Get friendly models (cannot be cached as they change during individual model movement)
    # Apply spatial filtering to friendly models
    friendly_models = []
    friendly_models_passable = []
    friendly_models_total = 0
    for unit in game_map.units:
        if not unit.is_alive() or not unit.deployed:
            continue
        if _units_share_army_identity(unit, moving_unit):  # Friendly unit
            unit_is_big = False
            if allow_move_over_friendly_big:
                try:
                    unit_is_big = bool(getattr(unit, "is_monster", False) or getattr(unit, "is_vehicle", False))
                except Exception:
                    unit_is_big = False
            for model_index, model in enumerate(_unit_models_for_collision(unit)):
                if not model.is_alive:
                    continue

                # Skip the specific model that's currently being moved
                if moving_model and model == moving_model:
                    continue

                friendly_models_total += 1
                model_pos = (model.model_base.x, model.model_base.y)

                # Apply spatial filtering
                if not is_within_search_area(model_pos):
                    continue

                model_shape = model.model_base.get_base_shape()
                platform_polygon = emplacement_platform_polygons.get(_unit_root_key(unit))
                if platform_polygon is not None:
                    adjusted_shape = model_shape.difference(platform_polygon)
                    if adjusted_shape.is_empty:
                        continue
                    model_shape = adjusted_shape

                if unit == moving_unit:
                    # For the moving unit, only include models that have already been moved
                    if _is_moved(model_index, model):
                        if unit_is_big:
                            friendly_models_passable.append(model_shape)
                        else:
                            friendly_models.append(model_shape)
                    # Skip models that haven't been moved yet (they shouldn't block)
                else:
                    # Include all models from other friendly units
                    if unit_is_big:
                        friendly_models_passable.append(model_shape)
                    else:
                        friendly_models.append(model_shape)

    # Build trees based on movement type
    trees = {
        'terrain': STRtree(blocking_terrain) if blocking_terrain else None,
        'friendly_models': STRtree(friendly_models) if friendly_models else None,
        'friendly_models_passable': STRtree(friendly_models_passable) if friendly_models_passable else None,
        'enemy_models': STRtree(enemy_models) if enemy_models else None,
        'enemy_aircraft_models': STRtree(enemy_aircraft_models) if enemy_aircraft_models else None,
    }
    if blocking_enemy_models:
        trees['enemy_models_blocking'] = STRtree(blocking_enemy_models)

    # Add engagement range buffers based on movement type.
    overrun_normal_move = bool(
        movement_type == MovementType.CONSOLIDATE and _tyranids_overrun_normal_move_active(moving_unit)
    )
    if movement_type in [MovementType.MOVE, MovementType.ADVANCE] or overrun_normal_move:
        # Standard movement: 1" engagement range buffer around enemy models
        if all_enemy_shapes:
            if enemy_cache_key in _enemy_engagement_buffer_cache:
                all_buffered = _enemy_engagement_buffer_cache[enemy_cache_key]
            else:
                all_buffered = [shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL) for shape in all_enemy_shapes]
                _enemy_engagement_buffer_cache[enemy_cache_key] = all_buffered

            buffered_enemies = [shape for shape in all_buffered if is_within_search_area(shape)]
            if buffered_enemies:
                trees['engagement_buffer'] = STRtree(buffered_enemies)

    elif movement_type == MovementType.SCOUT:
        # Scout movement: 9" buffer around enemy models and deployment zone
        if enemy_models:
            buffered_enemies = [shape.buffer(9.0) for shape in enemy_models]
            trees['engagement_buffer'] = STRtree(buffered_enemies)

        # Add deployment zone buffer (9" from enemy deployment zone)
        # Note: Deployment zone validation is handled separately in the Game class
        # For now, skip deployment zone buffer in pathfinding - this will be validated
        # at a higher level by the scout movement validation in the Game class
        pass

    elif movement_type == MovementType.CHARGE:
        # Charge: no engagement range buffer (can move into engagement range)
        pass  # Use base trees without engagement buffer

    elif movement_type in [MovementType.PILE_IN, MovementType.CONSOLIDATE]:
        # Pile-in/Consolidate: 3" movement, no engagement buffer
        pass  # Use base trees without engagement buffer

    # Aircraft engagement buffers (for final-position checks across movement types)
    if all_enemy_aircraft_shapes:
        if enemy_cache_key in _enemy_aircraft_engagement_buffer_cache:
            all_aircraft_buffered = _enemy_aircraft_engagement_buffer_cache[enemy_cache_key]
        else:
            all_aircraft_buffered = [shape.buffer(ENGAGEMENT_RANGE_HORIZONTAL) for shape in all_enemy_aircraft_shapes]
            _enemy_aircraft_engagement_buffer_cache[enemy_cache_key] = all_aircraft_buffered

        buffered_aircraft = [shape for shape in all_aircraft_buffered if is_within_search_area(shape)]
        if buffered_aircraft:
            trees['engagement_buffer_aircraft'] = STRtree(buffered_aircraft)

    return trees


def _tyranids_overrun_normal_move_active(moving_unit: 'Unit') -> bool:
    if moving_unit is None:
        return False
    try:
        sr = getattr(moving_unit, "special_rules", None)
    except Exception:
        return False
    if not isinstance(sr, dict):
        return False
    if not bool(sr.get("tyranids_overrun_normal_move_active")):
        return False

    phase_name = ""
    current_turn = 0
    current_owner = ""
    try:
        army = moving_unit.get_parent_army()
    except Exception:
        army = None
    try:
        player = getattr(army, "player", None) if army is not None else None
        current_owner = str(getattr(player, "id", "") or "").strip()
        game = getattr(player, "game", None) if player is not None else None
    except Exception:
        game = None
    if game is not None:
        try:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
    try:
        marked_turn = int(sr.get("tyranids_overrun_turn", 0) or 0)
    except Exception:
        marked_turn = 0
    marked_owner = str(sr.get("tyranids_overrun_turn_owner", "") or "").strip()
    exp = str(sr.get("tyranids_overrun_expires_phase", "") or "").strip().upper()

    if exp and phase_name and exp != phase_name:
        return False
    if marked_turn and current_turn and marked_turn != current_turn:
        return False
    if marked_owner and current_owner and marked_owner != current_owner:
        return False
    return True


def get_validation_rules(
    movement_type: MovementType,
    target_unit: 'Unit' = None,
    *,
    moving_unit: 'Unit' = None,
    target_units: Optional[list['Unit']] = None,
    movement_profile: Optional[MovementProfile] = None,
) -> dict:
    """
    Get validation rules for specific movement types.

    Args:
        movement_type: Type of movement being performed
        target_unit: Target unit for charge movement (required for CHARGE)

    Returns:
        Dict containing validation rules for this movement type
    """
    if movement_profile is None:
        movement_profile = build_movement_profile(
            moving_unit,
            movement_type,
            target_unit=target_unit,
            target_units=target_units,
        )

    # Base rules that apply to all movement types
    base_rules = {
        'prevent_friendly_overlap': True,    # Always prevent friendly model overlap
        'prevent_enemy_overlap': True,       # Always prevent enemy model overlap
        'apply_pivot_cost': movement_profile.pivot_cost_mode != "none",
        'check_terrain_traversal': True,    # Always check if unit can traverse terrain
        'can_move_through_enemy_models': bool(movement_profile.can_move_through_enemy_models),
        'can_move_through_friendly_models': bool(movement_profile.can_move_through_friendly_models),
        'can_move_through_terrain': False,
        'movement_profile': movement_profile,
        'free_climb_height_inches': float(movement_profile.free_climb_height_inches),
        'can_end_on_upper_surfaces': bool(movement_profile.can_end_on_upper_surfaces),
        # Aircraft rule: cannot end any move within Engagement Range of enemy AIRCRAFT (charge exception handled below).
        'cannot_end_within_engagement_range_of_aircraft': True,
    }

    # Add movement-specific rules
    if movement_type == MovementType.CHARGE:
        targets = list(target_units or [])
        if not targets and target_unit is not None:
            targets = [target_unit]
        base_rules.update({
            'must_end_in_engagement_range': False,
            'target_unit': targets[0] if targets else target_unit,  # Legacy single-target consumers
            'charge_target_units': targets,
            'charge_target_unit_ids': {get_entity_id(t) for t in targets if t is not None},
            'allow_engagement_range_movement': True,  # Can move through engagement range
            'allow_base_to_base_contact': True,  # Can end in base-to-base contact with target(s)
        })
        try:
            can_fly = bool(moving_unit is not None and getattr(moving_unit, "is_flying", False))
        except Exception:
            can_fly = False
        if can_fly:
            try:
                if any(bool(getattr(t, "is_aircraft", False)) for t in targets if t is not None):
                    base_rules['allow_end_in_engagement_range_of_aircraft'] = True
            except Exception:
                pass

    elif movement_type == MovementType.PILE_IN:
        from .constants import PILE_IN_DISTANCE
        pile_in_distance = PILE_IN_DISTANCE
        try:
            if moving_unit is not None and hasattr(moving_unit, "get_fight_phase_move_distance_override"):
                override = moving_unit.get_fight_phase_move_distance_override("pile_in")
                if override is not None:
                    pile_in_distance = float(override)
        except Exception:
            pass
        base_rules.update({
            'must_end_closer_to_enemies': True,
            'prefer_base_contact': True,  # Prefer ending in base-to-base contact
            'max_distance_override': pile_in_distance,  # Standard pile-in distance (or override)
            'apply_pivot_cost': True,
            # Pathfinding is discretized; allow a tiny epsilon so an intended 3.0" move doesn't get rejected as 3.04".
            'distance_tolerance': 0.05,
        })
        try:
            if moving_unit is not None and not bool(getattr(moving_unit, "is_flying", False)):
                base_rules['closest_enemy_unit_exclude_keywords'] = {"AIRCRAFT"}
        except Exception:
            pass
        try:
            if moving_unit is not None:
                army = moving_unit.get_parent_army()
                mgr = getattr(army, "templar_vows", None) if army is not None else None
                if mgr is not None and mgr.use_closest_enemy_unit_rule(moving_unit):
                    base_rules['closest_enemy_unit'] = True
        except Exception:
            pass
        try:
            if moving_unit is not None and hasattr(moving_unit, "get_choreographer_of_war_source"):
                source = str(moving_unit.get_choreographer_of_war_source() or "")
                if source:
                    base_rules['must_end_as_close_as_possible_to_closest_enemy_unit'] = True
                    base_rules['closest_enemy_unit_reason'] = source
                    base_rules['must_end_closer_to_enemies'] = False
                    base_rules['must_end_closer_to_enemies_or_objectives'] = False
        except Exception:
            pass

    elif movement_type == MovementType.CONSOLIDATE:
        from .constants import CONSOLIDATE_DISTANCE
        consolidate_distance = CONSOLIDATE_DISTANCE
        try:
            if moving_unit is not None and hasattr(moving_unit, "get_fight_phase_move_distance_override"):
                override = moving_unit.get_fight_phase_move_distance_override("consolidate")
                if override is not None:
                    consolidate_distance = float(override)
        except Exception:
            pass
        base_rules.update({
            'must_end_closer_to_enemies_or_objectives': True,
            'prefer_base_contact': True,  # Prefer ending in base-to-base contact
            'max_distance_override': consolidate_distance,  # Standard consolidate distance (or override)
            'apply_pivot_cost': True,
            # Pathfinding is discretized; allow a tiny epsilon so an intended 3.0" move doesn't get rejected as 3.04".
            'distance_tolerance': 0.05,
        })
        try:
            if moving_unit is not None:
                sr = getattr(moving_unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("stratagem_consolidate_requires_engagement"):
                    base_rules['consolidate_requires_engagement'] = True
                if isinstance(sr, dict) and sr.get("space_marines_hearts_hardened_to_duty_active"):
                    base_rules['consolidate_ignore_closest_enemy_requirement'] = True
                if isinstance(sr, dict):
                    allowed_objective_ids = [
                        str(value or "").strip()
                        for value in list(sr.get("stratagem_consolidate_allowed_objective_ids", []) or [])
                        if str(value or "").strip()
                    ]
                    if allowed_objective_ids:
                        base_rules['consolidate_allowed_objective_ids'] = list(allowed_objective_ids)
        except Exception:
            pass
        try:
            if moving_unit is not None and not bool(getattr(moving_unit, "is_flying", False)):
                base_rules['closest_enemy_unit_exclude_keywords'] = {"AIRCRAFT"}
        except Exception:
            pass
        try:
            if moving_unit is not None:
                army = moving_unit.get_parent_army()
                mgr = getattr(army, "templar_vows", None) if army is not None else None
                if mgr is not None and mgr.use_closest_enemy_unit_rule(moving_unit):
                    base_rules['closest_enemy_unit'] = True
        except Exception:
            pass
        try:
            if moving_unit is not None and hasattr(moving_unit, "get_choreographer_of_war_source"):
                source = str(moving_unit.get_choreographer_of_war_source() or "")
                if source:
                    base_rules['must_end_as_close_as_possible_to_closest_enemy_unit'] = True
                    base_rules['closest_enemy_unit_reason'] = source
                    base_rules['must_end_closer_to_enemies'] = False
                    base_rules['must_end_closer_to_enemies_or_objectives'] = False
        except Exception:
            pass
        if _tyranids_overrun_normal_move_active(moving_unit):
            normal_move_distance = 6.0
            try:
                sr = getattr(moving_unit, "special_rules", None)
                if isinstance(sr, dict):
                    normal_move_distance = float(sr.get("tyranids_overrun_normal_move_distance", 6.0) or 6.0)
            except Exception:
                normal_move_distance = 6.0
            base_rules['max_distance_override'] = max(
                float(base_rules.get("max_distance_override", 0.0) or 0.0),
                float(normal_move_distance),
            )
            base_rules['must_end_closer_to_enemies_or_objectives'] = False
            base_rules['prefer_base_contact'] = False
            base_rules['consolidate_requires_engagement'] = False
            base_rules['cannot_move_within_engagement_range'] = True
            base_rules['cannot_end_in_engagement_range'] = True

    elif movement_type in (
        MovementType.BLOOD_SURGE,
        MovementType.BRAZEN_FURY,
        MovementType.HORDE_MOVE,
        MovementType.BLISTERING_ASSAULT,
        MovementType.BESTIAL_RAGE,
    ):
        horde_move_rule = None
        if movement_type == MovementType.HORDE_MOVE and moving_unit is not None:
            rule_fn = getattr(moving_unit, "get_horde_move_rule", None)
            horde_move_rule = rule_fn() if callable(rule_fn) else None
            if not isinstance(horde_move_rule, dict):
                horde_move_rule = None
        if movement_type == MovementType.BLOOD_SURGE:
            reason = "Blood Surge"
        elif movement_type == MovementType.BRAZEN_FURY:
            reason = "Brazen Fury"
        elif movement_type == MovementType.BLISTERING_ASSAULT:
            reason = "Blistering Assault"
        elif movement_type == MovementType.BESTIAL_RAGE:
            reason = "Bestial Rage"
        else:
            reason = str((horde_move_rule or {}).get("source", "") or "Horde Move").strip() or "Horde Move"
        base_rules.update({
            'allow_engagement_range_movement': True,
            'must_end_as_close_as_possible_to_closest_enemy_unit': True,
            'closest_enemy_unit_reason': reason,
            # Pathfinding discretization can drift a touch; allow a tiny epsilon.
            'distance_tolerance': 0.05,
        })
        if movement_type in (MovementType.BLOOD_SURGE, MovementType.BRAZEN_FURY, MovementType.BESTIAL_RAGE):
            base_rules['closest_enemy_unit_exclude_keywords'] = {"AIRCRAFT"}
        if movement_type == MovementType.HORDE_MOVE and moving_unit is not None:
            exclude_keywords = {"AIRCRAFT"}
            if horde_move_rule is not None and "closest_enemy_unit_exclude_keywords" in horde_move_rule:
                exclude_keywords = set(horde_move_rule.get("closest_enemy_unit_exclude_keywords", ()) or ())
            if exclude_keywords:
                base_rules["closest_enemy_unit_exclude_keywords"] = exclude_keywords
            elif "closest_enemy_unit_exclude_keywords" in base_rules:
                base_rules.pop("closest_enemy_unit_exclude_keywords", None)
            if horde_move_rule is not None and bool(
                horde_move_rule.get("allow_closest_objective_marker_instead_of_closest_enemy_unit", False)
            ):
                base_rules["allow_closest_objective_marker_instead_of_closest_enemy_unit"] = True
                base_rules["closest_objective_marker_reason"] = str(
                    horde_move_rule.get("closest_objective_marker_reason", "") or reason
                ).strip() or reason
            sm_mgr = None
            try:
                army = moving_unit.get_parent_army()
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            except Exception:
                sm_mgr = None
            if not bool(base_rules.get("allow_closest_objective_marker_instead_of_closest_enemy_unit", False)):
                objective_override_fn = (
                    getattr(sm_mgr, "purge_and_sanctify_righteous_zeal_objective_override_applies", None)
                    if sm_mgr is not None
                    else None
                )
                if callable(objective_override_fn):
                    try:
                        if bool(objective_override_fn(moving_unit)):
                            base_rules["allow_closest_objective_marker_instead_of_closest_enemy_unit"] = True
                            base_rules["closest_objective_marker_reason"] = "Purge and Sanctify"
                    except Exception:
                        pass

    elif movement_type == MovementType.CAREEN:
        base_rules.update({
            'can_move_through_enemy_models': True,
            'cannot_move_within_engagement_range': False,
            'cannot_end_in_engagement_range': True,
        })

    elif movement_type == MovementType.FALL_BACK:
        base_rules.update({
            'can_move_through_enemy_models': True,  # Can move through enemy models
            'cannot_end_in_engagement_range': True,  # Cannot end within engagement range
            'check_desperate_escape': True,  # Check if Desperate Escape tests are needed
        })

    elif movement_type == MovementType.SCOUT:
        base_rules.update({
            'min_distance_from_enemies': 9.0,  # Must end 9" from enemies
            'min_distance_from_deployment_zone': 9.0,  # Must end 9" from enemy deployment
        })

    elif movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
        base_rules.update({
            'cannot_move_within_engagement_range': True,  # Cannot move within 1" of enemies
        })

    # Hammer of the Emperor (Astra Militarum): Iron Tread.
    # SQUADRON units can move within Engagement Range while Advancing, but cannot end there.
    if movement_type == MovementType.ADVANCE and moving_unit is not None:
        am_mgr = None
        try:
            army = moving_unit.get_parent_army()
        except Exception:
            army = None
        if army is not None:
            am_mgr = getattr(army, "astra_militarum_detachments", None)
        iron_tread_fn = (
            getattr(am_mgr, "iron_tread_allows_advance_move_within_engagement_range", None)
            if am_mgr is not None
            else None
        )
        if callable(iron_tread_fn) and bool(iron_tread_fn(moving_unit)):
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True

    # FLY: can move over enemy models for Normal/Advance/Fall Back/Charge moves.
    try:
        is_fly = bool(moving_unit is not None and moving_unit.is_flying)
    except Exception:
        is_fly = False
    if is_fly and _movement_type_allows_fly_over(movement_type):
        base_rules['can_move_through_enemy_models'] = True
        # FLY units can pass within engagement range while moving, but cannot end there.
        if movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True

    # Super-heavy Walker (Chaos Knights): move through models (excluding TITANIC), can pass within
    # engagement range but cannot end within it for Normal/Advance/Fall Back moves.
    try:
        is_super_heavy = bool(moving_unit is not None and moving_unit.has_super_heavy_walker())
    except Exception:
        is_super_heavy = False
    if is_super_heavy and movement_type in [MovementType.MOVE, MovementType.ADVANCE, MovementType.FALL_BACK]:
        base_rules['can_move_through_enemy_models'] = True
        base_rules['can_move_through_friendly_models'] = True
        base_rules['block_titanic_models'] = True
        if movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True

    # World Eaters enhancement (Vessels of Wrath): Gateways to Glory.
    # Normal/Advance/Charge: move horizontally through models and terrain.
    # Normal/Advance only: cannot end within Engagement Range.
    try:
        sr = getattr(moving_unit, "special_rules", None)
        has_gateways_to_glory = bool(isinstance(sr, dict) and sr.get("enhancement_gateways_to_glory"))
    except Exception:
        has_gateways_to_glory = False
    if not has_gateways_to_glory and moving_unit is not None:
        try:
            members = list(getattr(moving_unit, "get_attached_unit_members", lambda: [])() or [])
        except Exception:
            members = []
        for member in members:
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_gateways_to_glory"):
                has_gateways_to_glory = True
                break
    has_preternatural_agility = False
    try:
        fn = getattr(moving_unit, "_preternatural_agility_move_through_models_active", None)
        if callable(fn):
            has_preternatural_agility = bool(fn())
    except Exception:
        has_preternatural_agility = False
    if (has_gateways_to_glory or has_preternatural_agility) and movement_type in [MovementType.MOVE, MovementType.ADVANCE, MovementType.CHARGE]:
        base_rules['can_move_through_enemy_models'] = True
        base_rules['can_move_through_friendly_models'] = True
        base_rules['can_move_through_terrain'] = True
        base_rules['ignore_enemy_models_blocking'] = True
        if movement_type in [MovementType.MOVE, MovementType.ADVANCE]:
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True

    # Acrobatic Onslaught (Aeldari - Ghosts of the Webway):
    # Harlequins models can move through enemy models during Charge moves.
    aeldari_mgr = None
    if moving_unit is not None and hasattr(moving_unit, "get_parent_army"):
        army = moving_unit.get_parent_army()
        if army is not None:
            aeldari_mgr = getattr(army, "aeldari_detachments", None)
    acrobatic_applies_fn = (
        getattr(aeldari_mgr, "acrobatic_onslaught_charge_move_through_enemy_applies", None)
        if aeldari_mgr is not None
        else None
    )
    if movement_type == MovementType.CHARGE and callable(acrobatic_applies_fn) and bool(acrobatic_applies_fn(moving_unit)):
        base_rules['can_move_through_enemy_models'] = True
        base_rules['ignore_enemy_models_blocking'] = True

    def _coerce_move_types(value) -> set[str]:
        types: set[str] = set()
        if isinstance(value, str) and value:
            types.add(str(value))
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                if item:
                    types.add(str(item))
        return types

    warp_walker_move_types: set[str] = set()
    warp_walker_auto_pass_desperate_escape = False
    loathsome_dexterity_move_types: set[str] = set()
    loathsome_dexterity_auto_pass_desperate_escape = False
    if moving_unit is not None:
        try:
            members = list(getattr(moving_unit, "get_attached_unit_members", lambda: [])() or [])
        except Exception:
            members = []
        if not members:
            members = [moving_unit]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if sr.get("enhancement_warp_walker"):
                configured = _coerce_move_types(sr.get("enhancement_warp_walker_move_types"))
                if configured:
                    warp_walker_move_types.update(configured)
                else:
                    warp_walker_move_types.update({"move", "advance", "fall_back"})
                if bool(sr.get("enhancement_warp_walker_auto_pass_desperate_escape", False)):
                    warp_walker_auto_pass_desperate_escape = True
            if sr.get("enhancement_loathsome_dexterity"):
                configured = _coerce_move_types(sr.get("enhancement_loathsome_dexterity_move_types"))
                if configured:
                    loathsome_dexterity_move_types.update(configured)
                else:
                    loathsome_dexterity_move_types.update({"move", "advance", "fall_back"})
                if bool(sr.get("enhancement_loathsome_dexterity_auto_pass_desperate_escape", False)):
                    loathsome_dexterity_auto_pass_desperate_escape = True

    phase_move_types: set[str] = set()
    phase_move_enemy_models_only_types: set[str] = set()
    phase_move_models_only_types: set[str] = set()
    phase_move_models_only_block_titanic_types: set[str] = set()
    phase_move_terrain_only_types: set[str] = set()
    phase_engagement_types: set[str] = set()
    phase_move_block_titanic_types: set[str] = set()
    phase_move_block_monster_vehicle_types: set[str] = set()
    auto_pass_desperate_escape = False
    sr_sources: list[dict] = []
    seen_sr_ids: set[int] = set()
    try:
        sr = getattr(moving_unit, "special_rules", None)
    except Exception:
        sr = None
    if isinstance(sr, dict):
        sr_sources.append(sr)
        seen_sr_ids.add(id(sr))
    if moving_unit is not None:
        try:
            members = list(getattr(moving_unit, "get_attached_unit_members", lambda: [])() or [])
        except Exception:
            members = []
        for member in members:
            msr = getattr(member, "special_rules", None)
            if not isinstance(msr, dict):
                continue
            if id(msr) in seen_sr_ids:
                continue
            seen_sr_ids.add(id(msr))
            sr_sources.append(msr)
    for sr in sr_sources:
        phase_move_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_types")))
        phase_move_enemy_models_only_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_enemy_models_only_types")))
        phase_move_models_only_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_models_only_types")))
        phase_move_models_only_block_titanic_types.update(
            _coerce_move_types(sr.get("bearer_unit_phase_move_models_only_block_titanic_types"))
        )
        phase_move_terrain_only_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_terrain_only_types")))
        phase_engagement_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_engagement_types")))
        phase_move_block_titanic_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_block_titanic_types")))
        phase_move_block_monster_vehicle_types.update(_coerce_move_types(sr.get("bearer_unit_phase_move_block_monster_vehicle_types")))
        phase_move_types.update(_coerce_move_types(sr.get("titanic_phase_move_types")))
        phase_engagement_types.update(_coerce_move_types(sr.get("titanic_phase_move_engagement_types")))
        phase_move_block_titanic_types.update(_coerce_move_types(sr.get("titanic_phase_move_block_titanic_types")))
        if bool(sr.get("bearer_unit_auto_pass_desperate_escape")):
            auto_pass_desperate_escape = True

    move_tag = _movement_type_tag(movement_type)
    if move_tag and (move_tag in warp_walker_move_types or move_tag in loathsome_dexterity_move_types):
        base_rules['can_move_through_enemy_models'] = True
        if move_tag in ("move", "advance", "fall_back"):
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True
        if (
            (warp_walker_auto_pass_desperate_escape or loathsome_dexterity_auto_pass_desperate_escape)
            and move_tag == "fall_back"
        ):
            base_rules['check_desperate_escape'] = False

    if move_tag and move_tag in phase_move_enemy_models_only_types:
        base_rules['can_move_through_enemy_models'] = True
        base_rules['ignore_enemy_models_blocking'] = True
        if move_tag in phase_move_block_monster_vehicle_types:
            base_rules['block_monster_vehicle_models'] = True
        elif base_rules.get('block_monster_vehicle_models', False):
            base_rules['block_monster_vehicle_models'] = False
        if move_tag in ("move", "advance", "fall_back"):
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True

    if move_tag and move_tag in phase_move_models_only_types:
        base_rules['can_move_through_enemy_models'] = True
        base_rules['can_move_through_friendly_models'] = True
        base_rules['ignore_enemy_models_blocking'] = True
        if move_tag in phase_move_models_only_block_titanic_types:
            base_rules['block_titanic_models'] = True
        elif base_rules.get('block_titanic_models', False):
            base_rules['block_titanic_models'] = False

    if move_tag and move_tag in phase_move_types:
        base_rules['can_move_through_enemy_models'] = True
        base_rules['can_move_through_friendly_models'] = True
        base_rules['can_move_through_terrain'] = True
        base_rules['ignore_enemy_models_blocking'] = True
        if move_tag in phase_move_block_titanic_types:
            base_rules['block_titanic_models'] = True
        elif base_rules.get('block_titanic_models', False):
            base_rules['block_titanic_models'] = False
        if move_tag in phase_move_block_monster_vehicle_types:
            base_rules['block_monster_vehicle_models'] = True
        elif base_rules.get('block_monster_vehicle_models', False):
            base_rules['block_monster_vehicle_models'] = False
        # "Move through models" wording for Normal/Advance implies passing through Engagement Range,
        # but still not ending there.
        if move_tag in ("move", "advance"):
            base_rules['cannot_move_within_engagement_range'] = False
            base_rules['cannot_end_in_engagement_range'] = True
    elif move_tag and move_tag in phase_move_terrain_only_types:
        base_rules['can_move_through_terrain'] = True

    if move_tag and move_tag in phase_engagement_types:
        base_rules['cannot_move_within_engagement_range'] = False
        base_rules['cannot_end_in_engagement_range'] = True

    if auto_pass_desperate_escape and move_tag == "fall_back":
        base_rules['check_desperate_escape'] = False

    if base_rules.get('can_move_through_enemy_models') or base_rules.get('can_move_through_friendly_models'):
        base_rules['can_move_through_models'] = True

    return base_rules


def _segment_terrain_cache_key(
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    *,
    facing: float,
) -> Tuple[float, float, float, float, float]:
    sx = round(float(start[0]), 4)
    sy = round(float(start[1]), 4)
    ex = round(float(end[0]), 4)
    ey = round(float(end[1]), 4)
    if (sx, sy) <= (ex, ey):
        ax, ay, bx, by = sx, sy, ex, ey
    else:
        ax, ay, bx, by = ex, ey, sx, sy
    return (ax, ay, bx, by, round(float(facing), 4))


def _segment_crosses_blocking_terrain(
    *,
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
    model: 'Model',
    terrain_tree,
    cache: dict[Tuple[float, float, float, float, float], bool],
) -> bool:
    if terrain_tree is None:
        return False

    sx = float(start[0])
    sy = float(start[1])
    ex = float(end[0])
    ey = float(end[1])
    if abs(sx - ex) <= 1e-9 and abs(sy - ey) <= 1e-9:
        return False

    base = model.model_base
    facing = float(getattr(base, "facing", 0.0) or 0.0)
    key = _segment_terrain_cache_key(start, end, facing=facing)
    cached = cache.get(key)
    if cached is not None:
        return bool(cached)

    search_radius = max(0.01, float(base.get_longest_radius()))
    min_x = min(sx, ex) - search_radius
    max_x = max(sx, ex) + search_radius
    min_y = min(sy, ey) - search_radius
    max_y = max(sy, ey) + search_radius
    query_shape = box(min_x, min_y, max_x, max_y)
    potential_hits = query_spatial_index(terrain_tree, query_shape)
    if not potential_hits:
        cache[key] = False
        return False

    start_shape = base.get_base_shape_at(sx, sy, facing)
    end_shape = base.get_base_shape_at(ex, ey, facing)
    swept_shape = start_shape.union(end_shape).convex_hull
    for hit_shape in potential_hits:
        if swept_shape.intersects(hit_shape):
            cache[key] = True
            return True

    cache[key] = False
    return False

def a_star_unified(model: 'Model', target: Tuple[float, float, float], max_distance: float,
                  collision_trees: dict, validation_rules: dict, game_map: 'Map',
                  movement_type: MovementType) -> dict:
    """
    Unified A* pathfinding algorithm that uses STRTrees for collision detection
    and validation rules for movement-specific constraints.

    Args:
        model: The model to move
        target: Target position (x, y, z)
        max_distance: Maximum movement distance
        collision_trees: Dict of STRTrees for different collision types
        validation_rules: Dict of validation rules for this movement type
        game_map: The game map
        movement_type: Movement type for distance/vertical rules

    Returns:
        Dict with keys: 'valid', 'path', 'distance', 'reason'
    """
    import heapq

    unit = model.parent_unit
    start = (model.model_base.x, model.model_base.y, model.model_base.z)
    goal = (float(target[0]), float(target[1]), float(target[2]))
    base_facing = float(getattr(model.model_base, "facing", 0.0) or 0.0)
    moving_shape_template = model.model_base.get_base_shape_at(0.0, 0.0, base_facing)
    position_shape_cache: dict[Tuple[float, float], Polygon] = {}
    allow_through_terrain = bool(validation_rules.get('can_move_through_terrain', False))
    segment_terrain_cache: dict[Tuple[float, float, float, float, float], bool] = {}

    # PERFORMANCE OPTIMIZATION: Adaptive step size and iteration limits based on distance
    straight_line_distance_2d = heuristic_2d((start[0], start[1]), (goal[0], goal[1]))
    if straight_line_distance_2d <= 3.0:
        step_size = 0.3  # Smaller steps for short distances
        max_iterations = 5000
    elif straight_line_distance_2d <= 6.0:
        step_size = 0.4  # Medium steps for medium distances
        max_iterations = 8000
    else:
        step_size = 0.6  # Larger steps for long distances
        max_iterations = 12000

    logger.debug("A* params: distance=%.2f, step=%.3f, max_iter=%s", straight_line_distance_2d, step_size, max_iterations)

    def _snap_xy(x: float, y: float) -> Tuple[float, float]:
        # Quantize X/Y to a step grid anchored at the start position to avoid float drift.
        return (
            start[0] + round((x - start[0]) / step_size) * step_size,
            start[1] + round((y - start[1]) / step_size) * step_size,
        )

    snapped_start_xy = _snap_xy(start[0], start[1])
    start = (snapped_start_xy[0], snapped_start_xy[1], start[2])

    ignore_vertical = _unit_ignores_vertical_distance(unit, movement_type)
    fly_move = _unit_is_fly_move(unit, movement_type)

    # Surface resolution helpers (2.5D pathing across floors/ground).
    from warhammer40k_ai.battlefield.map import TerrainType, RuinsTerrain
    from ..utility.constants import RUINS_FLOOR_THICKNESS

    def _poly_contains(poly, point: Point) -> bool:
        try:
            if hasattr(poly, "covers"):
                return bool(poly.covers(point))
            return bool(poly.contains(point))
        except Exception:
            return False

    def _resolve_ruins_floor_option(pos: Tuple[float, float, float]) -> Optional[dict]:
        if game_map is None:
            return None
        try:
            point = Point(float(pos[0]), float(pos[1]))
        except Exception:
            return None
        for terrain in list(getattr(game_map, "terrain_features", []) or []):
            try:
                if getattr(terrain, "terrain_type", None) != TerrainType.RUINS:
                    continue
                if not _poly_contains(terrain.footprint, point):
                    continue
            except Exception:
                continue
            floors = getattr(terrain, "floors", []) or []
            best = None
            best_dist = float('inf')
            for fl in floors:
                poly = fl.get("polygon")
                if poly is None:
                    continue
                if not _poly_contains(poly, point):
                    continue
                surface = float(fl.get("elevation", 0.0) or 0.0) + float(fl.get("thickness", RUINS_FLOOR_THICKNESS) or RUINS_FLOOR_THICKNESS)
                dist = abs(float(pos[2]) - surface)
                if dist < best_dist and dist < 1.0:
                    best = {"polygon": poly, "surface_z": surface}
                    best_dist = dist
            if best is not None:
                return best
        return None

    start_floor = _resolve_ruins_floor_option(start)
    target_floor = _resolve_ruins_floor_option(goal)
    if start_floor and target_floor:
        try:
            if abs(float(start_floor["surface_z"]) - float(target_floor["surface_z"])) < 1e-6:
                if start_floor.get("polygon") is target_floor.get("polygon"):
                    target_floor = None
        except Exception:
            pass

    ground_cache = {}
    surface_cache = {}
    air_z = float(start[2])

    def _ground_height(x: float, y: float) -> float:
        key = (x, y)
        if key in ground_cache:
            return ground_cache[key]
        z = 0.0
        try:
            if game_map is not None:
                z = float(game_map.get_surface_height_for_model(model, x, y))
        except Exception:
            z = 0.0
        ground_cache[key] = z
        return z

    def _surface_options_for_point(x: float, y: float) -> List[float]:
        key = (x, y)
        if key in surface_cache:
            options = list(surface_cache[key])
        else:
            options = []
            options.extend(list(getattr(game_map, "get_surface_options_for_model", lambda *_args, **_kwargs: [_ground_height(x, y)])(model, x, y) or []))
            try:
                point = Point(float(x), float(y))
            except Exception:
                point = None

            if point is not None and start_floor is not None:
                if _poly_contains(start_floor.get("polygon"), point):
                    options.append(float(start_floor.get("surface_z", 0.0)))
            if point is not None and target_floor is not None:
                if _poly_contains(target_floor.get("polygon"), point):
                    options.append(float(target_floor.get("surface_z", 0.0)))

            # Deduplicate within a small tolerance.
            uniq = []
            for z in options:
                if all(abs(z - uz) > 1e-4 for uz in uniq):
                    uniq.append(z)
            surface_cache[key] = uniq
            options = list(uniq)

        if fly_move:
            if all(abs(air_z - z) > 1e-4 for z in options):
                options.append(air_z)
        return options

    # Snap goal Z to the nearest valid surface at that XY (prevents unreachable targets on elevated ground).
    try:
        goal_options = _surface_options_for_point(goal[0], goal[1])
        surface_only = []
        for z in goal_options:
            if fly_move and abs(z - air_z) <= 1e-4:
                continue
            surface_only.append(z)
        if surface_only:
            nearest = min(surface_only, key=lambda z: abs(float(goal[2]) - float(z)))
            goal = (goal[0], goal[1], float(nearest))
    except Exception:
        pass

    def _heuristic_cost(node: Tuple[float, float, float]) -> float:
        dx = float(goal[0]) - float(node[0])
        dy = float(goal[1]) - float(node[1])
        horiz = sqrt(dx * dx + dy * dy)
        if ignore_vertical or fly_move:
            return horiz
        dz = abs(float(goal[2]) - float(node[2]))
        threshold = get_freely_climbable_range(unit, movement_type)
        vertical = dz if dz > threshold else 0.0
        return horiz + vertical

    # Initialize A* data structures
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: _heuristic_cost(start)}
    closed_set = set()

    iterations = 0

    # Track collision reasons for better error reporting
    collision_reasons = set()

    logger.debug("Starting A* from %s to %s, max_distance=%s", start, goal, max_distance)

    # Optimization: Try straight line path first if no obstacles
    allow_straight_line = True
    if (not ignore_vertical) and (not fly_move) and game_map is not None:
        try:
            line = LineString([(start[0], start[1]), (goal[0], goal[1])])
            threshold = get_freely_climbable_range(unit, movement_type)
            for terrain in list(getattr(game_map, "terrain_features", []) or []):
                try:
                    if getattr(terrain, "terrain_type", None) == TerrainType.RUINS:
                        continue
                    if not line.intersects(terrain.footprint):
                        continue
                    height = getattr(terrain, "height", None)
                    if height is None:
                        height = getattr(terrain, "rim_height", 0.0)
                    if float(height or 0.0) > threshold:
                        allow_straight_line = False
                        break
                except Exception:
                    continue
        except Exception:
            allow_straight_line = False

    straight_line_distance = measure_direct_distance(start, goal, unit, movement_type, game_map)
    if allow_straight_line and straight_line_distance <= max_distance:
        # Special case: zero-distance move (staying in same position)
        if straight_line_distance == 0.0:
            # For zero-distance moves, we need to check if the current position is valid
            # This handles the case where another model has moved to this position
            validity_result = is_position_valid_unified_detailed(
                goal,
                model,
                collision_trees,
                validation_rules,
                game_map,
                is_final_position=True,
                position_shape_template=moving_shape_template,
                position_shape_cache=position_shape_cache,
            )
            if not validity_result['valid']:
                return {
                    'valid': False,
                    'path': [start],
                    'distance': 0.0,
                    'reason': validity_result['reason'],
                    'desperate_escape': {'required': False, 'reason': 'Not fall back movement'}
                }
            else:
                # Zero-distance move is valid
                return {
                    'valid': True,
                    'path': [start, goal],
                    'distance': 0.0,
                    'reason': 'Valid path found',
                    'desperate_escape': {'required': False, 'reason': 'Not fall back movement'}
                }

        # Check if straight line path is clear
        straight_line_clear = True
        num_checks = max(20, int(straight_line_distance_2d / (step_size / 2)))  # More frequent checks

        for i in range(1, num_checks):
            t = i / num_checks
            check_pos = (
                start[0] + t * (goal[0] - start[0]),
                start[1] + t * (goal[1] - start[1]),
                start[2] + t * (goal[2] - start[2])
            )
            validity_result = is_position_valid_unified_detailed(
                check_pos,
                model,
                collision_trees,
                validation_rules,
                game_map,
                is_final_position=False,
                position_shape_template=moving_shape_template,
                position_shape_cache=position_shape_cache,
            )
            if not validity_result['valid']:
                straight_line_clear = False
                collision_reasons.add(validity_result['reason'])
                break

        if (
            straight_line_clear
            and not allow_through_terrain
            and _segment_crosses_blocking_terrain(
                start=start,
                end=goal,
                model=model,
                terrain_tree=collision_trees.get('terrain'),
                cache=segment_terrain_cache,
            )
        ):
            straight_line_clear = False
            collision_reasons.add('Path crosses terrain between waypoints')

        if straight_line_clear:
            # Validate final position for straight line path using unified validation system
            validation_result = is_position_valid_unified_detailed(
                goal,
                model,
                collision_trees,
                validation_rules,
                game_map,
                is_final_position=True,
                position_shape_template=moving_shape_template,
                position_shape_cache=position_shape_cache,
            )
            if not validation_result['valid']:
                # Continue with A* pathfinding instead
                pass
            else:
                # Check for Desperate Escape requirements for straight line path
                desperate_escape_info = check_desperate_escape_requirements(
                    model, [start, goal], validation_rules, game_map
                )

                return {
                    'valid': True,
                    'path': [start, goal],
                    'distance': measure_path_distance([start, goal], unit, movement_type, game_map),
                    'reason': 'Straight line path',
                    'desperate_escape': desperate_escape_info
                }

    while open_set and iterations < max_iterations:
        current = heapq.heappop(open_set)[1]

        if current in closed_set:
            continue

        closed_set.add(current)

        # PERFORMANCE OPTIMIZATION: Early termination when close to goal
        distance_to_goal = heuristic(current, goal)
        if distance_to_goal < step_size:
            if (
                not allow_through_terrain
                and _segment_crosses_blocking_terrain(
                    start=current,
                    end=goal,
                    model=model,
                    terrain_tree=collision_trees.get('terrain'),
                    cache=segment_terrain_cache,
                )
            ):
                collision_reasons.add('Path crosses terrain between waypoints')
                iterations += 1
                continue

            # Reconstruct path
            path = []
            path_node = current
            while path_node in came_from:
                path.append(path_node)
                path_node = came_from[path_node]
            path.append(start)
            path.reverse()
            path.append(goal)  # Ensure we end exactly at goal

            # Calculate total distance using movement rules
            total_distance = measure_path_distance(path, unit, movement_type, game_map)

            # Apply pivot cost only if there's actual rotation
            if validation_rules.get('apply_pivot_cost', False) and len(path) > 1:
                # Check if the path requires rotation (direction change)
                requires_rotation = False
                if len(path) >= 3:  # Need at least 3 points to detect direction change
                    # Check if there are significant direction changes
                    for i in range(1, len(path) - 1):
                        prev_dir = (path[i][0] - path[i-1][0], path[i][1] - path[i-1][1])
                        next_dir = (path[i+1][0] - path[i][0], path[i+1][1] - path[i][1])

                        # Normalize directions
                        prev_len = (prev_dir[0]**2 + prev_dir[1]**2)**0.5
                        next_len = (next_dir[0]**2 + next_dir[1]**2)**0.5

                        if prev_len > 0 and next_len > 0:
                            prev_norm = (prev_dir[0]/prev_len, prev_dir[1]/prev_len)
                            next_norm = (next_dir[0]/next_len, next_dir[1]/next_len)

                            # Calculate angle between directions
                            dot_product = prev_norm[0]*next_norm[0] + prev_norm[1]*next_norm[1]
                            dot_product = max(-1, min(1, dot_product))  # Clamp to [-1, 1]
                            angle_diff = acos(dot_product)

                            # If angle change > 30 degrees, consider it rotation
                            if angle_diff > pi / 6:  # 30 degrees
                                requires_rotation = True
                                break

                if requires_rotation:
                    pivot_cost = get_pivot_cost(model.parent_unit)
                    if pivot_cost > 0:
                        total_distance += pivot_cost
                        logger.debug("Applied pivot cost: %.2f", pivot_cost)

            # Validate final position according to movement rules
            # Use the unified validation system that includes collision trees and engagement_buffer
            validation_result = is_position_valid_unified_detailed(
                goal,
                model,
                collision_trees,
                validation_rules,
                game_map,
                is_final_position=True,
                position_shape_template=moving_shape_template,
                position_shape_cache=position_shape_cache,
            )
            if not validation_result['valid']:
                return {
                    'valid': False,
                    'path': None,
                    'distance': total_distance,
                    'reason': validation_result['reason']
                }

            # Check distance limit
            max_dist = validation_rules.get('max_distance_override', max_distance)
            tol = 0.0
            try:
                tol = float(validation_rules.get("distance_tolerance", 0.0) or 0.0)
            except Exception:
                tol = 0.0
            if total_distance > (max_dist + tol):
                return {
                    'valid': False,
                    'path': None,
                    'distance': total_distance,
                    'reason': f'Path too long ({total_distance:.1f}" > {max_dist:.1f}")'
                }

            # Check for Desperate Escape requirements
            desperate_escape_info = check_desperate_escape_requirements(
                model, path, validation_rules, game_map
            )

            return {
                'valid': True,
                'path': path,
                'distance': total_distance,
                'reason': 'Valid path found',
                'desperate_escape': desperate_escape_info
            }

        # PERFORMANCE OPTIMIZATION: Prioritize neighbors that move toward goal (2D grid)
        all_neighbors = [(-step_size, 0), (step_size, 0), (0, -step_size), (0, step_size),
                        (-step_size, -step_size), (-step_size, step_size),
                        (step_size, -step_size), (step_size, step_size)]

        goal_direction = (goal[0] - current[0], goal[1] - current[1])
        goal_distance = (goal_direction[0]**2 + goal_direction[1]**2)**0.5

        if goal_distance > 0:
            goal_dir_norm = (goal_direction[0] / goal_distance, goal_direction[1] / goal_distance)
            neighbor_scores = []
            for dx, dy in all_neighbors:
                move_distance = (dx**2 + dy**2)**0.5
                if move_distance > 0:
                    move_dir_norm = (dx / move_distance, dy / move_distance)
                    alignment = goal_dir_norm[0] * move_dir_norm[0] + goal_dir_norm[1] * move_dir_norm[1]
                    score = alignment
                else:
                    score = 0
                neighbor_scores.append((score, dx, dy))

            neighbor_scores.sort(reverse=True)
            prioritized_neighbors = neighbor_scores[:6]
        else:
            prioritized_neighbors = [(0, dx, dy) for dx, dy in all_neighbors]

        neighbor_states = []
        current_x, current_y, current_z = current
        current_surface_opts = _surface_options_for_point(current_x, current_y)
        for z_opt in current_surface_opts:
            if abs(z_opt - current_z) > 1e-4:
                neighbor_states.append((current_x, current_y, z_opt))

        for _score, dx, dy in prioritized_neighbors:
            nx, ny = _snap_xy(current_x + dx, current_y + dy)
            for nz in _surface_options_for_point(nx, ny):
                neighbor_states.append((nx, ny, nz))

        for neighbor in neighbor_states:
            if neighbor in closed_set:
                continue

            validity_result = is_position_valid_unified_detailed(
                neighbor,
                model,
                collision_trees,
                validation_rules,
                game_map,
                is_final_position=False,
                position_shape_template=moving_shape_template,
                position_shape_cache=position_shape_cache,
            )
            if not validity_result['valid']:
                collision_reasons.add(validity_result['reason'])
                continue

            if (
                not allow_through_terrain
                and _segment_crosses_blocking_terrain(
                    start=current,
                    end=neighbor,
                    model=model,
                    terrain_tree=collision_trees.get('terrain'),
                    cache=segment_terrain_cache,
                )
            ):
                collision_reasons.add('Path crosses terrain between waypoints')
                continue

            tentative_g_score = g_score[current] + movement_segment_cost(current, neighbor, unit, movement_type)

            max_dist = validation_rules.get('max_distance_override', max_distance)
            if tentative_g_score > max_dist:
                continue

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + _heuristic_cost(neighbor)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

        iterations += 1

    # Provide more specific failure reason based on encountered obstacles
    if collision_reasons:
        primary_reason = list(collision_reasons)[0]  # Get first encountered reason
        if len(collision_reasons) > 1:
            reason = f"{primary_reason} (and {len(collision_reasons)-1} other obstacles)"
        else:
            reason = primary_reason
    else:
        reason = f'No path found after {iterations} iterations'

    return {
        'valid': False,
        'path': None,
        'distance': 0,
        'reason': reason
    }

def is_position_valid_unified_detailed(position: Tuple[float, float, float], model: 'Model',
                                      collision_trees: dict, validation_rules: dict, game_map: 'Map' = None, 
                                      is_final_position: bool = True,
                                      position_shape_template: Polygon | None = None,
                                      position_shape_cache: Optional[dict[Tuple[float, float], Polygon]] = None) -> dict:
    """
    Check if a position is valid using STRTrees and validation rules, returning detailed reason.

    Args:
        position: Position to check (x, y, z)
        model: The model being moved
        collision_trees: Dict of STRTrees for collision detection
        validation_rules: Dict of validation rules
        game_map: The game map
        is_final_position: Whether this is the final destination (affects charge/fall back validation)

    Returns:
        Dict with 'valid' (bool) and 'reason' (str) keys
    """
    px = float(position[0])
    py = float(position[1])
    shape_cache_key = (round(px, 4), round(py, 4))
    test_shape = None
    if position_shape_cache is not None:
        test_shape = position_shape_cache.get(shape_cache_key)

    if test_shape is None:
        if position_shape_template is not None:
            test_shape = translate(position_shape_template, px, py)
        else:
            facing = float(getattr(model.model_base, "facing", 0.0) or 0.0)
            test_shape = model.model_base.get_base_shape_at(px, py, facing)
        if position_shape_cache is not None:
            position_shape_cache[shape_cache_key] = test_shape

    # Check if the entire model base fits within battlefield boundaries
    if game_map:
        bounds = test_shape.bounds
        width = getattr(game_map, "width", None)
        height = getattr(game_map, "height", None)
        if width is not None and height is not None:
            if bounds[0] < 0.0 or bounds[1] < 0.0 or bounds[2] > float(width) or bounds[3] > float(height):
                return {'valid': False, 'reason': 'Position outside battlefield boundaries'}
        else:
            boundary = getattr(game_map, "boundary", None)
            if boundary is not None:
                if not boundary.contains(test_shape):
                    return {'valid': False, 'reason': 'Position outside battlefield boundaries'}
            elif not game_map.is_within_boundary(model, (px, py)):
                return {'valid': False, 'reason': 'Position outside battlefield boundaries'}
    else:
        # Fallback basic boundary check if no game_map provided
        bounds = test_shape.bounds  # (minx, miny, maxx, maxy)
        if bounds[0] < 0 or bounds[1] < 0:
            return {'valid': False, 'reason': 'Position outside battlefield boundaries'}

    # Check terrain collisions using shape intersection
    allow_through_terrain = bool(validation_rules.get('can_move_through_terrain', False))
    if collision_trees.get('terrain') and not (allow_through_terrain and not is_final_position):
        potential_hits = query_spatial_index(collision_trees['terrain'], test_shape)
        actual_hits = []

        for hit_shape in potential_hits:
            try:
                if test_shape.intersects(hit_shape):
                    actual_hits.append(hit_shape)
            except Exception:
                continue

        if actual_hits:
            return {'valid': False, 'reason': 'Position blocked by terrain'}

    allow_through_friendly = validation_rules.get(
        'can_move_through_friendly_models',
        validation_rules.get('can_move_through_models', False)
    )
    allow_through_enemy = validation_rules.get(
        'can_move_through_enemy_models',
        validation_rules.get('can_move_through_models', False)
    )

    def _friendly_overlap_blocked(tree) -> bool:
        if not tree:
            return False
        potential_hits = query_spatial_index(tree, test_shape)
        for hit_shape in potential_hits:
            try:
                if not test_shape.intersects(hit_shape):
                    continue
            except Exception:
                continue

            allow_due_to_vertical_separation = False
            if game_map:
                for unit in game_map.units:
                    if not _units_share_army_identity(unit, model.parent_unit):
                        continue
                    for other_model in unit.models:
                        if other_model is model or not other_model.is_alive:
                            continue
                        try:
                            other_shape = other_model.model_base.get_base_shape()
                            if test_shape.intersects(other_shape):
                                # Use exact model heights via Base.vertical_distance to determine separation sufficiency
                                from ..utility.model_base import clone_base as _clone_base
                                from ..utility.placement_validation import bases_overlap_3d as _bases_overlap_3d
                                temp_base = _clone_base(model.model_base)
                                temp_base.set_position(position[0], position[1], position[2])
                                temp_base.set_facing(getattr(model.model_base, 'facing', 0.0))
                                if not _bases_overlap_3d(temp_base, other_model.model_base):
                                    allow_due_to_vertical_separation = True
                                break
                        except Exception:
                            continue
                    if allow_due_to_vertical_separation:
                        break
            if allow_due_to_vertical_separation:
                continue
            return True
        return False

    # Super-heavy Walker: cannot move through TITANIC models.
    if validation_rules.get('block_titanic_models', False) and game_map is not None:
        for unit in list(getattr(game_map, "units", []) or []):
            if unit is model.parent_unit:
                continue
            try:
                if not getattr(unit, "is_titanic", False):
                    continue
            except Exception:
                continue
            try:
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
            except Exception:
                continue
            for other_model in list(getattr(unit, "models", []) or []):
                try:
                    if not getattr(other_model, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    other_shape = other_model.model_base.get_base_shape()
                    if test_shape.intersects(other_shape):
                        return {'valid': False, 'reason': 'Position blocked by TITANIC model'}
                except Exception:
                    continue

    # Optional rule: cannot move through enemy MONSTER/VEHICLE models.
    if validation_rules.get('block_monster_vehicle_models', False) and game_map is not None:
        for unit in list(getattr(game_map, "units", []) or []):
            if unit is model.parent_unit:
                continue
            if _units_share_army_identity(unit, model.parent_unit):
                continue
            try:
                is_monster = bool(getattr(unit, "is_monster", False))
                is_vehicle = bool(getattr(unit, "is_vehicle", False))
                has_any_keyword = getattr(unit, "has_any_keyword", None)
                if callable(has_any_keyword):
                    is_monster = is_monster or bool(has_any_keyword("MONSTER"))
                    is_vehicle = is_vehicle or bool(has_any_keyword("VEHICLE"))
            except Exception:
                continue
            if not (is_monster or is_vehicle):
                continue
            try:
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
            except Exception:
                continue
            for other_model in list(getattr(unit, "models", []) or []):
                try:
                    if not getattr(other_model, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    other_shape = other_model.model_base.get_base_shape()
                    if test_shape.intersects(other_shape):
                        return {'valid': False, 'reason': 'Position blocked by MONSTER/VEHICLE model'}
                except Exception:
                    continue

    # Check friendly model collisions using shape intersection with 3D consideration
    if collision_trees.get('friendly_models') and validation_rules.get('prevent_friendly_overlap', True):
        if (not allow_through_friendly) or is_final_position:
            if _friendly_overlap_blocked(collision_trees['friendly_models']):
                return {'valid': False, 'reason': 'Position blocked by friendly models'}

    if collision_trees.get('friendly_models_passable') and validation_rules.get('prevent_friendly_overlap', True):
        if is_final_position:
            if _friendly_overlap_blocked(collision_trees['friendly_models_passable']):
                return {'valid': False, 'reason': 'Position blocked by friendly models'}

    # For FLY non-MONSTER/VEHICLE: still block enemy MONSTER/VEHICLE models during movement.
    ignore_enemy_models_blocking = bool(validation_rules.get('ignore_enemy_models_blocking', False))
    if collision_trees.get('enemy_models_blocking') and not is_final_position and not ignore_enemy_models_blocking:
        potential_hits = query_spatial_index(collision_trees['enemy_models_blocking'], test_shape)
        for hit_shape in potential_hits:
            try:
                if test_shape.intersects(hit_shape):
                    return {'valid': False, 'reason': 'Position blocked by enemy models'}
            except Exception:
                continue

    # Check enemy model collisions using shape intersection
    if collision_trees.get('enemy_models') and validation_rules.get('prevent_enemy_overlap', True):
        if (not allow_through_enemy) or is_final_position:
            potential_hits = query_spatial_index(collision_trees['enemy_models'], test_shape)
            actual_hits = []

            # Track if we've already allowed base-to-base contact with target unit(s)
            allowed_target_contact = False

            for hit_shape in potential_hits:
                try:
                    if test_shape.intersects(hit_shape):
                        # For charges, allow base-to-base contact with target unit
                        if validation_rules.get('allow_base_to_base_contact', False) and is_final_position and not allowed_target_contact:
                            target_units = list(validation_rules.get('charge_target_units', []) or [])
                            if not target_units:
                                target_unit = validation_rules.get('target_unit')
                                if target_unit is not None:
                                    target_units = [target_unit]
                            if target_units:
                                # Check if this hit is from any target unit by checking spatial proximity
                                # Since we're at the final position and it's a charge, any enemy model
                                # that's very close is likely a target unit
                                for tu in target_units:
                                    for enemy_model in tu.models:
                                        if enemy_model.is_alive:
                                            # Calculate edge-to-edge distance to this enemy model
                                            from ..utility.model_base import clone_base
                                            temp_base = clone_base(model.model_base)
                                            temp_base.set_position(position[0], position[1], position[2])

                                            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                                            horizontal_distance = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
                                            vertical_distance = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))

                                            # For base-to-base contact, we want edge-to-edge distance to be very close to 0
                                            # but not negative (which would indicate overlap)
                                            if (horizontal_distance >= 0.0 and horizontal_distance < 0.1 and 
                                                vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                                                allowed_target_contact = True
                                                continue
                        if not allowed_target_contact:
                            actual_hits.append(hit_shape)
                except Exception:
                    continue

            if actual_hits:
                if allow_through_enemy and is_final_position and validation_rules.get('cannot_end_in_engagement_range', False):
                    return {'valid': False, 'reason': 'Position within engagement range of enemy models'}
                return {'valid': False, 'reason': 'Position blocked by enemy models'}

    # Check enemy AIRCRAFT overlaps (always ignored during movement, but not at final position)
    if collision_trees.get('enemy_aircraft_models') and validation_rules.get('prevent_enemy_overlap', True):
        if is_final_position:
            potential_hits = query_spatial_index(collision_trees['enemy_aircraft_models'], test_shape)
            actual_hits = []
            allowed_target_contact = False

            for hit_shape in potential_hits:
                try:
                    if test_shape.intersects(hit_shape):
                        if validation_rules.get('allow_base_to_base_contact', False) and not allowed_target_contact:
                            target_units = list(validation_rules.get('charge_target_units', []) or [])
                            if not target_units:
                                target_unit = validation_rules.get('target_unit')
                                if target_unit is not None:
                                    target_units = [target_unit]
                            for tu in target_units:
                                if not bool(getattr(tu, "is_aircraft", False)):
                                    continue
                                for enemy_model in tu.models:
                                    if enemy_model.is_alive:
                                        from ..utility.model_base import clone_base
                                        temp_base = clone_base(model.model_base)
                                        temp_base.set_position(position[0], position[1], position[2])
                                        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                                        horizontal_distance = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
                                        vertical_distance = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))
                                        if (horizontal_distance >= 0.0 and horizontal_distance < 0.1 and
                                            vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                                            allowed_target_contact = True
                                            continue
                        if not allowed_target_contact:
                            actual_hits.append(hit_shape)
                except Exception:
                    continue

            if actual_hits:
                return {'valid': False, 'reason': 'Position blocked by enemy aircraft'}

    # Check engagement range using fast spatial indexing (engagement_buffer tree)
    if validation_rules.get('cannot_move_within_engagement_range', False):
        # Use the pre-built engagement_buffer STRtree for O(log n) performance instead of O(n)
        if collision_trees and 'engagement_buffer' in collision_trees and collision_trees['engagement_buffer']:
            # Query the engagement buffer tree with the shape and confirm real intersections
            potential_hits = query_spatial_index(collision_trees['engagement_buffer'], test_shape)
            for hit in potential_hits:
                try:
                    if test_shape.intersects(hit):
                        logger.debug("Final position rejected due to engagement range (fast spatial check)")
                        return {'valid': False, 'reason': 'Position within engagement range of enemy models'}
                except Exception:
                    continue
        else:
            # No engagement buffer tree available. Given our spatial filtering builds the
            # buffer using a radius that already includes any enemy that could be within
            # engagement range of any valid destination, the absence of the tree implies
            # no relevant enemies are in range. Skip slow O(n) checks.
            pass

    # Aircraft engagement range restriction (final position only, unless allowed by charge vs aircraft)
    if validation_rules.get('cannot_end_within_engagement_range_of_aircraft', False) and is_final_position:
        if not validation_rules.get('allow_end_in_engagement_range_of_aircraft', False):
            if collision_trees and collision_trees.get('engagement_buffer_aircraft'):
                try:
                    potential_hits = query_spatial_index(collision_trees['engagement_buffer_aircraft'], test_shape)
                    for hit in potential_hits:
                        try:
                            if test_shape.intersects(hit):
                                return {'valid': False, 'reason': 'Position within engagement range of enemy aircraft'}
                        except Exception:
                            continue
                except Exception:
                    pass
            elif game_map is not None:
                # Check enemy aircraft models directly
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                from ..utility.model_base import clone_base
                temp_base = clone_base(model.model_base)
                temp_base.set_position(position[0], position[1], position[2])
                try:
                    temp_base.set_facing(float(getattr(model.model_base, "facing", 0.0) or 0.0))
                except Exception:
                    pass
                for unit in getattr(game_map, 'units', []) or []:
                    if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                        continue
                    try:
                        if not bool(getattr(unit, "is_aircraft", False)):
                            continue
                    except Exception:
                        continue
                    for enemy_model in getattr(unit, "models", []) or []:
                        if not getattr(enemy_model, "is_alive", False):
                            continue
                        horiz = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
                        vert = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))
                        if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                            return {'valid': False, 'reason': 'Position within engagement range of enemy aircraft'}

    # Charge: cannot end within Engagement Range of non-target enemies.
    charge_target_ids = set(validation_rules.get('charge_target_unit_ids', set()) or set())
    if charge_target_ids and is_final_position and game_map is not None:
        from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
        from ..utility.model_base import clone_base
        temp_base = clone_base(model.model_base)
        temp_base.set_position(position[0], position[1], position[2])
        try:
            temp_base.set_facing(float(getattr(model.model_base, "facing", 0.0) or 0.0))
        except Exception:
            pass
        for unit in list(getattr(game_map, "units", []) or []):
            if unit is None:
                continue
            if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                continue
            if get_entity_id(unit) in charge_target_ids:
                continue
            for enemy_model in getattr(unit, "models", []) or []:
                if not getattr(enemy_model, "is_alive", False):
                    continue
                horiz = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
                vert = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))
                if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                    return {'valid': False, 'reason': 'Position within engagement range of non-target enemy unit'}

    # Check charge-specific rules (only apply to final positions)
    if validation_rules.get('must_end_in_engagement_range', False) and is_final_position:
        target_unit = validation_rules.get('target_unit')
        if not target_unit:
            return {'valid': False, 'reason': 'No target unit specified for charge'}

        # Check if final position is within engagement range of target unit using edge-to-edge distance
        from ..utility.model_base import clone_base
        temp_base = clone_base(model.model_base)
        temp_base.set_position(position[0], position[1], position[2])
        # Preserve facing for non-circular bases (elliptical/hull) so edge distance is correct.
        try:
            temp_base.set_facing(float(getattr(model.model_base, "facing", 0.0) or 0.0))
        except Exception:
            pass
        in_engagement_range = False
        for enemy_model in target_unit.models:
            if not enemy_model.is_alive:
                continue
            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            horizontal_distance = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
            vertical_distance = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))
            if (horizontal_distance <= ENGAGEMENT_RANGE_HORIZONTAL and
                vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                in_engagement_range = True
                break

        if not in_engagement_range:
            return {'valid': False, 'reason': 'Charge must end within engagement range of target unit'}

    # Check fall back rules (only apply to final positions)
    if validation_rules.get('cannot_end_in_engagement_range', False) and is_final_position:
        from ..utility.model_base import clone_base
        temp_base = clone_base(model.model_base)
        temp_base.set_position(position[0], position[1], position[2])
        try:
            temp_base.set_facing(float(getattr(model.model_base, "facing", 0.0) or 0.0))
        except Exception:
            pass
        # Check against all enemy models using proper edge-to-edge distance
        for unit in game_map.units:
            if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                continue
            for enemy_model in unit.models:
                if not enemy_model.is_alive:
                    continue
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                horizontal_distance = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
                vertical_distance = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))
                # Use a strict "<" here to match the rest of the unified validation system and tests.
                # This avoids rejecting destinations that are exactly at 1.0" edge-to-edge due to float jitter.
                if (horizontal_distance < ENGAGEMENT_RANGE_HORIZONTAL and
                    vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                    logger.debug(
                        "Fall back validation - %s would end within engagement range of %s",
                        getattr(model, "name", "?"),
                        getattr(enemy_model, "name", "?"),
                    )
                    return {'valid': False, 'reason': 'Fall back cannot end within engagement range'}

    # Check RUINS terrain placement rules only for final positions
    if is_final_position and game_map and hasattr(game_map, 'terrain_features'):
        from warhammer40k_ai.battlefield.map import validate_ruins_placement
        ruins_validation = validate_ruins_placement(model.parent_unit, position, game_map.terrain_features, moving_model=model)
        if not ruins_validation['valid']:
            return {'valid': False, 'reason': f"RUINS placement invalid: {ruins_validation['reason']}"}
        special_surface_validation = getattr(game_map, "validate_model_surface_placement", None)
        if callable(special_surface_validation):
            surface_validation = special_surface_validation(model, position)
            if not surface_validation.get("valid", False):
                return {'valid': False, 'reason': str(surface_validation.get('reason', 'Invalid elevated-surface placement'))}

    # Note: Deployment zone validation for scout movement is handled at a higher level
    # by the Game class validation methods, not in the pathfinding system
    
    # Apply movement-type-specific final-position validation (pile-in, consolidate, scout, etc.)
    # This is intentionally done here because the pathfinding system (including the straight-line
    # fast path) relies on `is_position_valid_unified_detailed` to validate the destination.
    if is_final_position and game_map is not None:
        final_validation = validate_final_position(model, position, validation_rules, game_map)
        if not final_validation.get('valid', False):
            return final_validation

    return {'valid': True, 'reason': 'Position is valid'}

def _entity_key(entity: object) -> str:
    try:
        return str(get_entity_id(entity))
    except ValueError:
        return f"object:{id(entity)}"


def _path_point_to_pose(point: object, *, default_facing: float) -> Optional[Pose]:
    if point is None:
        return None
    if isinstance(point, Pose):
        return point

    if hasattr(point, "x") and hasattr(point, "y"):
        try:
            x = float(getattr(point, "x"))
            y = float(getattr(point, "y"))
        except (TypeError, ValueError):
            return None
        try:
            z = float(getattr(point, "z", 0.0) or 0.0)
        except (TypeError, ValueError):
            z = 0.0
        try:
            facing = float(getattr(point, "facing", default_facing) or default_facing)
        except (TypeError, ValueError):
            facing = float(default_facing)
        return Pose(x=x, y=y, z=z, facing=facing)

    if not isinstance(point, (tuple, list)) or len(point) < 2:
        return None

    try:
        x = float(point[0])
        y = float(point[1])
    except (TypeError, ValueError, IndexError):
        return None
    try:
        z = float(point[2]) if len(point) > 2 else 0.0
    except (TypeError, ValueError):
        z = 0.0
    try:
        facing = float(point[3]) if len(point) > 3 else float(default_facing)
    except (TypeError, ValueError):
        facing = float(default_facing)
    return Pose(x=x, y=y, z=z, facing=facing)


def _path_to_sweep_poses(model: 'Model', path: List[Tuple[float, float, float]]) -> tuple[Pose, ...]:
    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return ()
    try:
        default_facing = float(getattr(model_base, "facing", 0.0) or 0.0)
    except (TypeError, ValueError):
        default_facing = 0.0

    poses: list[Pose] = []
    for point in list(path or []):
        pose = _path_point_to_pose(point, default_facing=default_facing)
        if pose is None:
            continue
        poses.append(pose)
    return tuple(poses)


def _path_z_segments(poses: tuple[Pose, ...]) -> tuple[tuple[float, float], ...]:
    if not poses:
        return ()
    if len(poses) == 1:
        z = float(poses[0].z)
        return ((z, z),)
    segments: list[tuple[float, float]] = []
    for index in range(1, len(poses)):
        start = poses[index - 1]
        end = poses[index]
        z_min = min(float(start.z), float(end.z))
        z_max = max(float(start.z), float(end.z))
        segments.append((z_min, z_max))
    return tuple(segments)


def _segments_overlap_enemy_vertical(
    z_segments: tuple[tuple[float, float], ...],
    *,
    enemy_z: float,
    enemy_height: float,
    moving_height: float,
) -> bool:
    max_height = max(float(enemy_height), float(moving_height))
    for z_min, z_max in z_segments:
        if z_max < float(enemy_z) - max_height:
            continue
        if z_min > float(enemy_z) + max_height:
            continue
        return True
    return False


def _enemy_units_for_moved_over(model: 'Model', game_map: 'Map') -> list['Unit']:
    unit = getattr(model, "parent_unit", None)
    if unit is None or game_map is None:
        return []

    get_enemy_units = getattr(game_map, "get_enemy_units", None)
    if callable(get_enemy_units):
        try:
            return list(get_enemy_units(unit) or [])
        except (TypeError, AttributeError):
            pass

    all_units = list(getattr(game_map, "units", ()) or ())
    return [
        test_unit
        for test_unit in all_units
        if test_unit is not None and not _units_share_army_identity(test_unit, unit)
    ]


def _unit_is_valid_enemy_for_move_over(enemy_unit: 'Unit') -> bool:
    if enemy_unit is None:
        return False
    is_alive_fn = getattr(enemy_unit, "is_alive", None)
    if callable(is_alive_fn) and not bool(is_alive_fn()):
        return False
    if not bool(getattr(enemy_unit, "deployed", True)):
        return False
    is_in_reserves_fn = getattr(enemy_unit, "is_in_reserves", None)
    if callable(is_in_reserves_fn) and bool(is_in_reserves_fn()):
        return False
    if bool(getattr(enemy_unit, "is_embarked", False)):
        return False
    return True


def _enemy_models_moved_over_by_sweep(
    model: 'Model',
    path: List[Tuple[float, float, float]],
    game_map: 'Map',
    *,
    require_vertical_overlap: bool,
) -> List['Model']:
    if model is None or game_map is None:
        return []
    if not path or len(path) < 2:
        return []

    model_base = getattr(model, "model_base", None)
    if model_base is None:
        return []

    enemy_units = _enemy_units_for_moved_over(model, game_map)
    if not enemy_units:
        return []

    poses = _path_to_sweep_poses(model, path)
    if len(poses) < 2:
        return []

    swept_shape = swept_footprint(poses, model_base)
    z_segments = _path_z_segments(poses)
    try:
        moving_height = float(getattr(model_base, "model_height", 0.0) or 0.0)
    except (TypeError, ValueError):
        moving_height = 0.0

    moved_records: list[tuple[str, 'Model']] = []
    seen_model_ids: set[str] = set()
    for enemy_unit in list(enemy_units or []):
        if not _unit_is_valid_enemy_for_move_over(enemy_unit):
            continue
        for enemy_model in list(getattr(enemy_unit, "models", ()) or ()):
            if enemy_model is None or not bool(getattr(enemy_model, "is_alive", False)):
                continue
            model_id = _entity_key(enemy_model)
            if model_id in seen_model_ids:
                continue
            base = getattr(enemy_model, "model_base", None)
            if base is None:
                continue
            if not swept_shape.intersects(base.get_base_shape()):
                continue
            if require_vertical_overlap:
                try:
                    enemy_z = float(getattr(base, "z", 0.0) or 0.0)
                except (TypeError, ValueError):
                    enemy_z = 0.0
                try:
                    enemy_height = float(getattr(base, "model_height", 0.0) or 0.0)
                except (TypeError, ValueError):
                    enemy_height = 0.0
                if not _segments_overlap_enemy_vertical(
                    z_segments,
                    enemy_z=enemy_z,
                    enemy_height=enemy_height,
                    moving_height=moving_height,
                ):
                    continue
            seen_model_ids.add(model_id)
            moved_records.append((model_id, enemy_model))

    moved_records.sort(key=lambda item: item[0])
    return [enemy_model for _, enemy_model in moved_records]


def check_desperate_escape_requirements(model: 'Model', path: List[Tuple[float, float, float]],
                                       validation_rules: dict, game_map: 'Map') -> dict:
    """
    Check if Desperate Escape tests are required for fall back movement.

    Args:
        model: The model that moved
        path: The movement path taken
        validation_rules: Movement validation rules
        game_map: The game map

    Returns:
        Dict with desperate escape information
    """
    if not validation_rules.get('check_desperate_escape', False):
        return {'required': False, 'reason': 'Not fall back movement'}

    unit = getattr(model, "parent_unit", None)
    if unit is None:
        return {'required': False, 'reason': 'No parent unit'}

    # Rule 1: Battle-shocked units always need Desperate Escape tests.
    if bool(getattr(unit, "is_battle_shocked", lambda: False)()):
        return {
            'required': True,
            'reason': 'Battle-shocked unit falling back',
            'all_models': True,
            'path_through_enemy': False,
        }

    path_through_enemy = bool(
        get_enemy_models_moved_over(
            model,
            path,
            game_map,
            require_vertical_overlap=True,
        )
    )

    # Rule 2: TITANIC/FLY units are exempt from moved-through Desperate Escape tests.
    if path_through_enemy:
        if bool(getattr(unit, "is_titanic", False)) or bool(getattr(unit, "is_flying", False)):
            return {
                'required': False,
                'reason': 'TITANIC or FLY unit exempt from Desperate Escape',
                'path_through_enemy': True,
            }
        return {
            'required': True,
            'reason': 'Path goes through enemy models',
            'all_models': False,
            'path_through_enemy': True,
        }

    return {
        'required': False,
        'reason': 'Path does not go through enemy models',
        'path_through_enemy': False,
    }


def get_enemy_units_moved_over(
    model: 'Model',
    path: List[Tuple[float, float, float]],
    game_map: 'Map',
    *,
    require_vertical_overlap: bool = True,
) -> List['Unit']:
    """
    Return enemy unit roots that the model moved over along the given path.
    """
    moved_models = get_enemy_models_moved_over(
        model,
        path,
        game_map,
        require_vertical_overlap=require_vertical_overlap,
    )
    if not moved_models:
        return []

    moved_unit_roots: list[tuple[str, 'Unit']] = []
    seen_root_ids: set[str] = set()
    for enemy_model in moved_models:
        enemy_unit = getattr(enemy_model, "parent_unit", None)
        if enemy_unit is None:
            continue
        get_root = getattr(enemy_unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else enemy_unit
        root_id = _entity_key(root)
        if root_id in seen_root_ids:
            continue
        seen_root_ids.add(root_id)
        moved_unit_roots.append((root_id, root))
    moved_unit_roots.sort(key=lambda item: item[0])
    return [unit_root for _, unit_root in moved_unit_roots]


def get_enemy_models_moved_over(
    model: 'Model',
    path: List[Tuple[float, float, float]],
    game_map: 'Map',
    *,
    require_vertical_overlap: bool = True,
) -> List['Model']:
    """
    Return individual enemy models that the moving model crossed over along the path.
    """
    return _enemy_models_moved_over_by_sweep(
        model,
        path,
        game_map,
        require_vertical_overlap=bool(require_vertical_overlap),
    )

def validate_final_position(model: 'Model', position: Tuple[float, float, float],
                          validation_rules: dict, game_map: 'Map') -> dict:
    """
    Validate the final position according to movement-specific rules.

    Args:
        model: The model being moved
        position: Final position to validate (x, y, z)
        validation_rules: Dict of validation rules
        game_map: The game map

    Returns:
        Dict with keys: 'valid', 'reason'
    """
    # Check charge-specific rules
    if validation_rules.get('must_end_in_engagement_range', False):
        target_unit = validation_rules.get('target_unit')
        if not target_unit:
            return {'valid': False, 'reason': 'No target unit specified for charge'}

        # Check if final position is within engagement range of target unit using edge-to-edge distance
        # Create a temporary model base at the final position to check engagement range
        from ..utility.model_base import clone_base
        temp_base = clone_base(model.model_base)
        temp_base.set_position(position[0], position[1], position[2])

        in_engagement_range = False
        for enemy_model in target_unit.models:
            if not enemy_model.is_alive:
                continue

            # Calculate edge-to-edge distance (same as engagement detection)
            from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
            horizontal_distance = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
            vertical_distance = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))

            # Check if within engagement range using same method as engagement detection
            if (horizontal_distance < ENGAGEMENT_RANGE_HORIZONTAL and
                vertical_distance <= 5.0):  # 5" vertical engagement range
                in_engagement_range = True
                logger.debug(
                    "Charge validation - %s within engagement range of %s (horizontal=%.2f, vertical=%.2f)",
                    getattr(model, "name", "?"),
                    getattr(enemy_model, "name", "?"),
                    horizontal_distance,
                    vertical_distance,
                )
                break

        if not in_engagement_range:
            return {'valid': False, 'reason': 'Charge must end within engagement range of target unit'}

    # Check fall back rules
    if validation_rules.get('cannot_end_in_engagement_range', False):
        # Check if final position is within engagement range of any enemy using edge-to-edge distance
        # Create a temporary model base at the final position to check engagement range
        from ..utility.model_base import clone_base
        temp_base = clone_base(model.model_base)
        temp_base.set_position(position[0], position[1], position[2])

        # Check against all enemy models using proper edge-to-edge distance
        for unit in game_map.units:
            if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                continue
            for enemy_model in unit.models:
                if not enemy_model.is_alive:
                    continue

                # Calculate edge-to-edge distance (same as engagement detection)
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                horizontal_distance = float(horizontal_distance_between_bases_2d(temp_base, enemy_model.model_base))
                vertical_distance = float(vertical_distance_between_bases(temp_base, enemy_model.model_base))

                # Check if within engagement range using same method as engagement detection
                if (horizontal_distance < ENGAGEMENT_RANGE_HORIZONTAL and
                    vertical_distance <= 5.0):  # 5" vertical engagement range
                    logger.debug(
                        "Fall back validation - %s would end within engagement range of %s (horizontal=%.2f, vertical=%.2f)",
                        getattr(model, "name", "?"),
                        getattr(enemy_model, "name", "?"),
                        horizontal_distance,
                        vertical_distance,
                    )
                    return {'valid': False, 'reason': 'Fall back cannot end within engagement range'}

    # Check pile-in/consolidate rules
    if validation_rules.get('must_end_closer_to_enemies', False):
        # Pile-in validation: model must end closer to at least one enemy model
        current_pos = model.get_location()
        if not current_pos:
            return {'valid': False, 'reason': 'Cannot determine current model position'}
        
        # Create temporary bases for distance calculations
        from ..utility.model_base import clone_base
        current_base = clone_base(model.model_base)
        current_base.set_position(current_pos[0], current_pos[1], current_pos[2])

        new_base = clone_base(model.model_base)
        new_base.set_position(position[0], position[1], position[2])
        
        # Find enemy models within potential pile-in range for optimization
        # Only consider enemies within (ENGAGEMENT_RANGE + PILE_IN_DISTANCE) of current position
        from .constants import PILE_IN_DISTANCE
        max_relevant_distance = ENGAGEMENT_RANGE_HORIZONTAL + PILE_IN_DISTANCE
        
        use_unit = bool(validation_rules.get('closest_enemy_unit', False))
        try:
            exclude_keywords = set(validation_rules.get('closest_enemy_unit_exclude_keywords', []) or [])
        except Exception:
            exclude_keywords = set()

        if use_unit:
            enemy_units = []
            for unit in game_map.units:
                if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                    continue
                if exclude_keywords:
                    try:
                        if any(unit.has_any_keyword(kw) for kw in exclude_keywords):
                            continue
                    except Exception:
                        try:
                            if "AIRCRAFT" in exclude_keywords and getattr(unit, "is_aircraft", False):
                                continue
                        except Exception:
                            pass
                try:
                    unit_models = [m for m in unit.models if getattr(m, "is_alive", False)]
                except Exception:
                    unit_models = []
                if not unit_models:
                    continue
                from ..utility.aura_utils import distance_between_bases_3d
                current_distance = min(float(distance_between_bases_3d(current_base, m.model_base)) for m in unit_models)
                if current_distance <= max_relevant_distance:
                    enemy_units.append((unit, current_distance, unit_models))
                else:
                    logger.debug(
                        "Excluding %s from pile-in validation - too far away (%.2f > %.2f)",
                        getattr(unit, "name", "?"),
                        current_distance,
                        max_relevant_distance,
                    )

            if not enemy_units:
                return {'valid': False, 'reason': 'No enemy units within pile-in range for validation'}

            enemy_units.sort(key=lambda entry: entry[1])
            closest_unit, closest_distance, closest_models = enemy_units[0]

            closest_model = None
            closest_model_dist = float('inf')
            from ..utility.aura_utils import distance_between_bases_3d
            for em in closest_models:
                d = float(distance_between_bases_3d(current_base, em.model_base))
                if d < closest_model_dist:
                    closest_model_dist = d
                    closest_model = em

            if closest_model is None:
                return {'valid': False, 'reason': 'No closest enemy model found for pile-in validation'}

            new_distance_to_unit = min(float(distance_between_bases_3d(new_base, em.model_base)) for em in closest_models)
            if new_distance_to_unit >= closest_distance:
                return {'valid': False, 'reason': f'Pile-in must end closer to closest enemy unit ({closest_unit.name}): {new_distance_to_unit:.2f}" >= {closest_distance:.2f}"'}

            logger.debug(
                "Pile-in validation - %s moved closer to %s: %.2f -> %.2f",
                getattr(model, "name", "?"),
                getattr(closest_unit, "name", "?"),
                closest_distance,
                new_distance_to_unit,
            )

            from .constants import BASE_CONTACT_EPSILON
            if validation_rules.get('prefer_base_contact', False):
                pile_in_distance = validation_rules.get('max_distance_override', PILE_IN_DISTANCE)
                if closest_distance <= pile_in_distance:
                    if new_distance_to_unit > BASE_CONTACT_EPSILON:
                        return {'valid': False, 'reason': f'Pile-in must end in base contact with closest enemy unit ({closest_unit.name}) when possible'}
                    logger.debug(
                        "Pile-in achieved required base contact with %s (distance=%.3f)",
                        getattr(closest_unit, "name", "?"),
                        new_distance_to_unit,
                    )
        else:
            enemy_models = []
            for unit in game_map.units:
                if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                    continue
                if exclude_keywords:
                    try:
                        if any(unit.has_any_keyword(kw) for kw in exclude_keywords):
                            continue
                    except Exception:
                        try:
                            if "AIRCRAFT" in exclude_keywords and getattr(unit, "is_aircraft", False):
                                continue
                        except Exception:
                            pass
                for enemy_model in unit.models:
                    if enemy_model.is_alive:
                        # Optimization: exclude enemies too far away to matter for pile-in
                        from ..utility.aura_utils import distance_between_bases_3d
                        current_distance = float(distance_between_bases_3d(current_base, enemy_model.model_base))
                        if current_distance <= max_relevant_distance:
                            enemy_models.append(enemy_model)
                        # Debug: show excluded enemies
                        else:
                            logger.debug(
                                "Excluding %s from pile-in validation - too far away (%.2f > %.2f)",
                                getattr(enemy_model, "name", "?"),
                                current_distance,
                                max_relevant_distance,
                            )

            if not enemy_models:
                return {'valid': False, 'reason': 'No enemy models within pile-in range for validation'}

            logger.debug(
                "Pile-in validation considering %s enemy models within %.2f range",
                len(enemy_models),
                max_relevant_distance,
            )

            # Find the closest enemy model to current position
            closest_enemy = None
            closest_distance = float('inf')
            for enemy_model in enemy_models:
                from ..utility.aura_utils import distance_between_bases_3d
                current_distance = float(distance_between_bases_3d(current_base, enemy_model.model_base))
                if current_distance < closest_distance:
                    closest_distance = current_distance
                    closest_enemy = enemy_model

            if not closest_enemy:
                return {'valid': False, 'reason': 'No closest enemy model found for pile-in validation'}

            logger.debug(
                "Closest enemy to %s is %s at %.2f",
                getattr(model, "name", "?"),
                getattr(closest_enemy, "name", "?"),
                closest_distance,
            )

            # Check if new position is closer to the CLOSEST enemy model
            from ..utility.aura_utils import distance_between_bases_3d
            new_distance_to_closest = float(distance_between_bases_3d(new_base, closest_enemy.model_base))

            if new_distance_to_closest >= closest_distance:
                return {'valid': False, 'reason': f'Pile-in must end closer to closest enemy ({closest_enemy.name}): {new_distance_to_closest:.2f}" >= {closest_distance:.2f}"'}

            logger.debug(
                "Pile-in validation - %s moved closer to %s: %.2f -> %.2f",
                getattr(model, "name", "?"),
                getattr(closest_enemy, "name", "?"),
                closest_distance,
                new_distance_to_closest,
            )

            # Check if base-to-base contact is possible and required
            from .constants import BASE_CONTACT_EPSILON
            if validation_rules.get('prefer_base_contact', False):
                # Calculate if it's possible to reach base contact with the closest enemy within pile-in distance
                enemy_position = closest_enemy.get_location()
                if enemy_position:
                    # Distance from model's current position to closest point on enemy base
                    max_distance_to_enemy = closest_distance
                    pile_in_distance = validation_rules.get('max_distance_override', PILE_IN_DISTANCE)

                    # If base contact is achievable within pile-in distance, require it
                    if max_distance_to_enemy <= pile_in_distance:
                        if new_distance_to_closest > BASE_CONTACT_EPSILON:
                            return {'valid': False, 'reason': f'Pile-in must end in base contact with closest enemy ({closest_enemy.name}) when possible'}
                        logger.debug(
                            "Pile-in achieved required base contact with %s (distance=%.3f)",
                            getattr(closest_enemy, "name", "?"),
                            new_distance_to_closest,
                        )
                    else:
                        logger.debug(
                            "Base contact not required - closest enemy too far (%.2f > %.2f)",
                            max_distance_to_enemy,
                            pile_in_distance,
                        )

    if validation_rules.get('must_end_as_close_as_possible_to_closest_enemy_unit', False):
        current_pos = model.get_location()
        if not current_pos:
            return {'valid': False, 'reason': 'Cannot determine current model position'}

        from ..utility.model_base import clone_base
        current_base = clone_base(model.model_base)
        current_base.set_position(current_pos[0], current_pos[1], current_pos[2])

        new_base = clone_base(model.model_base)
        new_base.set_position(position[0], position[1], position[2])

        exclude_keywords = set()
        try:
            exclude_keywords = set(validation_rules.get('closest_enemy_unit_exclude_keywords', []) or [])
        except Exception:
            exclude_keywords = set()
        allow_objective_override = bool(
            validation_rules.get("allow_closest_objective_marker_instead_of_closest_enemy_unit", False)
        )
        objective_reason_label = str(
            validation_rules.get("closest_objective_marker_reason", "") or "closest objective marker"
        )

        def _objective_override_ok() -> bool:
            if not allow_objective_override:
                return False
            objectives = []
            for objective in list(getattr(game_map, "objectives", []) or []):
                location = getattr(objective, "location", None) or objective
                if location is None or bool(getattr(location, "removed", False)):
                    continue
                objectives.append(location)
            if not objectives:
                return False

            closest_objective = None
            closest_distance = None
            for location in objectives:
                try:
                    ox = float(getattr(location, "x", 0.0))
                    oy = float(getattr(location, "y", 0.0))
                except Exception:
                    continue
                dx = current_base.x - ox
                dy = current_base.y - oy
                current_distance = sqrt((dx * dx) + (dy * dy))
                if closest_distance is None or current_distance < closest_distance:
                    closest_distance = current_distance
                    closest_objective = location
            if closest_objective is None or closest_distance is None:
                return False

            try:
                max_dist = float(validation_rules.get('blood_surge_max_distance', 0) or 0)
            except Exception:
                max_dist = 0.0
            if max_dist <= 0:
                try:
                    max_dist = float(validation_rules.get('max_distance_override', 0) or 0)
                except Exception:
                    max_dist = 0.0

            min_possible = max(0.0, float(closest_distance) - float(max_dist))
            try:
                tol = float(validation_rules.get("distance_tolerance", 0.0) or 0.0)
            except Exception:
                tol = 0.0

            try:
                ox = float(getattr(closest_objective, "x", 0.0))
                oy = float(getattr(closest_objective, "y", 0.0))
            except Exception:
                return False
            dx_new = new_base.x - ox
            dy_new = new_base.y - oy
            new_distance = sqrt((dx_new * dx_new) + (dy_new * dy_new))
            return new_distance <= (min_possible + tol)

        enemy_units = []
        for unit in getattr(game_map, 'units', []) or []:
            if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                continue
            if exclude_keywords:
                try:
                    if any(unit.has_any_keyword(kw) for kw in exclude_keywords):
                        continue
                except Exception:
                    try:
                        if "AIRCRAFT" in exclude_keywords and getattr(unit, "is_aircraft", False):
                            continue
                    except Exception:
                        pass
            try:
                unit_models = [m for m in unit.models if getattr(m, "is_alive", False)]
            except Exception:
                unit_models = []
            if not unit_models:
                continue
            from ..utility.aura_utils import distance_between_bases_3d
            current_distance = min(float(distance_between_bases_3d(current_base, m.model_base)) for m in unit_models)
            enemy_units.append((unit, current_distance, unit_models))

        if not enemy_units:
            if _objective_override_ok():
                return {'valid': True, 'reason': f'Valid final position ({objective_reason_label})'}
            return {'valid': False, 'reason': 'No enemy units available for Blood Surge validation'}

        enemy_units.sort(key=lambda entry: entry[1])
        closest_unit, closest_distance, closest_models = enemy_units[0]

        from ..utility.aura_utils import distance_between_bases_3d
        new_distance_to_unit = min(float(distance_between_bases_3d(new_base, m.model_base)) for m in closest_models)

        try:
            max_dist = float(validation_rules.get('blood_surge_max_distance', 0) or 0)
        except Exception:
            max_dist = 0.0
        if max_dist <= 0:
            try:
                max_dist = float(validation_rules.get('max_distance_override', 0) or 0)
            except Exception:
                max_dist = 0.0

        min_possible = max(0.0, float(closest_distance) - float(max_dist))
        try:
            tol = float(validation_rules.get("distance_tolerance", 0.0) or 0.0)
        except Exception:
            tol = 0.0
        if new_distance_to_unit > (min_possible + tol):
            if _objective_override_ok():
                return {'valid': True, 'reason': f'Valid final position ({objective_reason_label})'}
            reason_label = str(validation_rules.get("closest_enemy_unit_reason", "") or "Blood Surge")
            return {
                'valid': False,
                'reason': (
                    f'{reason_label} must end as close as possible to closest enemy unit '
                    f'({closest_unit.name}): {new_distance_to_unit:.2f}" > {min_possible:.2f}"'
                )
            }

    if validation_rules.get('must_end_closer_to_enemies_or_objectives', False):
        # Consolidate validation (10th edition):
        # - Each model must end closer to the closest enemy model
        # - If it is possible to end within Engagement Range of an enemy unit, the model must do so
        # - If not possible, the model may instead end closer to the closest objective marker and within range of it
        current_pos = model.get_location()
        if not current_pos:
            return {'valid': False, 'reason': 'Cannot determine current model position'}

        from ..utility.model_base import clone_base
        current_base = clone_base(model.model_base)
        current_base.set_position(current_pos[0], current_pos[1], current_pos[2])

        new_base = clone_base(model.model_base)
        new_base.set_position(position[0], position[1], position[2])

        from .constants import CONSOLIDATE_DISTANCE, BASE_CONTACT_EPSILON
        from ..utility.constants import ENGAGEMENT_RANGE_VERTICAL
        from shapely.geometry import Point as _ShPoint
        try:
            max_dist = float(validation_rules.get('max_distance_override', CONSOLIDATE_DISTANCE) or CONSOLIDATE_DISTANCE)
        except Exception:
            max_dist = CONSOLIDATE_DISTANCE
        requires_engagement = bool(validation_rules.get('consolidate_requires_engagement', False))
        ignore_closest_enemy_requirement = bool(
            validation_rules.get('consolidate_ignore_closest_enemy_requirement', False)
        )

        # Helper: determine if new position is within engagement range of ANY enemy model
        def _is_in_engagement_range_of_any_enemy(enemy_models: list) -> bool:
            for em in enemy_models:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                horiz = float(horizontal_distance_between_bases_2d(new_base, em.model_base))
                vert = float(vertical_distance_between_bases(new_base, em.model_base))
                if horiz <= ENGAGEMENT_RANGE_HORIZONTAL and vert <= ENGAGEMENT_RANGE_VERTICAL:
                    return True
            return False

        # Find relevant enemy models (optimize to those that could be reached into engagement)
        max_relevant_distance = ENGAGEMENT_RANGE_HORIZONTAL + max_dist
        try:
            exclude_keywords = set(validation_rules.get('closest_enemy_unit_exclude_keywords', []) or [])
        except Exception:
            exclude_keywords = set()
        enemy_models = []
        closest_enemy_model = None
        closest_enemy_distance = None
        for unit in getattr(game_map, 'units', []) or []:
            if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                continue
            if exclude_keywords:
                try:
                    if any(unit.has_any_keyword(kw) for kw in exclude_keywords):
                        continue
                except Exception:
                    try:
                        if "AIRCRAFT" in exclude_keywords and getattr(unit, "is_aircraft", False):
                            continue
                    except Exception:
                        pass
            for enemy_model in getattr(unit, 'models', []) or []:
                if not getattr(enemy_model, 'is_alive', False):
                    continue
                # Filter to models that matter for "engagement possible" check
                from ..utility.aura_utils import distance_between_bases_3d
                dist = float(distance_between_bases_3d(current_base, enemy_model.model_base))
                if closest_enemy_distance is None or dist < closest_enemy_distance:
                    closest_enemy_distance = dist
                    closest_enemy_model = enemy_model
                if dist <= max_relevant_distance:
                    enemy_models.append(enemy_model)

        def _objective_fallback_ok() -> bool:
            objs = list(getattr(game_map, "objectives", []) or [])
            allowed_objective_ids = {
                str(value or "").strip()
                for value in list(validation_rules.get("consolidate_allowed_objective_ids", []) or [])
                if str(value or "").strip()
            }
            if allowed_objective_ids:
                objs = [
                    obj
                    for obj in list(objs or [])
                    if str(resolve_objective_id(obj) or "").strip() in allowed_objective_ids
                ]
            if not objs:
                return False
            best_surface = None
            best_dist = None
            current_point = Point(float(current_base.x or 0.0), float(current_base.y or 0.0))
            for obj in objs:
                site = resolve_objective_site(obj)
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
                    d_cur = float(shape.distance(current_point))
                else:
                    dx = float(current_base.x or 0.0) - float(centroid[0] if len(centroid) > 0 else 0.0)
                    dy = float(current_base.y or 0.0) - float(centroid[1] if len(centroid) > 1 else 0.0)
                    d_cur = sqrt((dx * dx) + (dy * dy))
                if best_dist is None or d_cur < best_dist:
                    best_dist = d_cur
                    best_surface = (site, shape, centroid)
            if best_surface is None or best_dist is None:
                return False
            _best_site, best_shape, best_centroid = best_surface
            new_shape_getter = getattr(new_base, "get_base_shape", None)
            new_shape = new_shape_getter() if callable(new_shape_getter) else None
            if best_shape is not None and new_shape is not None:
                within = bool(new_shape.intersects(best_shape))
                d_new = float(best_shape.distance(Point(float(new_base.x or 0.0), float(new_base.y or 0.0))))
            else:
                ox = float(best_centroid[0] if len(best_centroid) > 0 else 0.0)
                oy = float(best_centroid[1] if len(best_centroid) > 1 else 0.0)
                radius = float(getattr(resolve_objective_site(_best_site), "control_radius", 3.0) or 0.0)
                dx = float(new_base.x or 0.0) - ox
                dy = float(new_base.y or 0.0) - oy
                d_new = sqrt((dx * dx) + (dy * dy))
                try:
                    base_r = float(new_base.get_longest_radius())
                except Exception:
                    try:
                        base_r = float(new_base.get_radius())
                    except Exception:
                        base_r = float(getattr(new_base, "radius", 0.0) or 0.0)
                within = d_new <= (radius + base_r + 1e-6)
            closer = d_new < (best_dist - 1e-6)
            return within and closer

        if not enemy_models and not requires_engagement:
            if closest_enemy_distance is not None and closest_enemy_distance > max_relevant_distance:
                if _objective_fallback_ok():
                    return {'valid': True, 'reason': 'Valid final position (objective fallback)'}
                return {
                    'valid': False,
                    'reason': 'Consolidate must end closer to an eligible objective marker and within range of it'
                }

        use_unit = bool(validation_rules.get('closest_enemy_unit', False))

        if requires_engagement and not _is_in_engagement_range_of_any_enemy(enemy_models):
            return {
                'valid': False,
                'reason': 'Consolidate must end within engagement range of an enemy unit'
            }

        if enemy_models:
            if use_unit:
                enemy_units = []
                for unit in getattr(game_map, 'units', []) or []:
                    if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                        continue
                    if exclude_keywords:
                        try:
                            if any(unit.has_any_keyword(kw) for kw in exclude_keywords):
                                continue
                        except Exception:
                            try:
                                if "AIRCRAFT" in exclude_keywords and getattr(unit, "is_aircraft", False):
                                    continue
                            except Exception:
                                pass
                    try:
                        unit_models = [m for m in unit.models if getattr(m, "is_alive", False)]
                    except Exception:
                        unit_models = []
                    if not unit_models:
                        continue
                    from ..utility.aura_utils import distance_between_bases_3d
                    min_dist = min(float(distance_between_bases_3d(current_base, m.model_base)) for m in unit_models)
                    if min_dist <= max_relevant_distance:
                        enemy_units.append((unit, min_dist, unit_models))

                if enemy_units:
                    enemy_units.sort(key=lambda entry: entry[1])
                    closest_unit, closest_distance, closest_models = enemy_units[0]

                    engagement_possible = closest_distance <= max_relevant_distance
                    in_engagement = _is_in_engagement_range_of_any_enemy(enemy_models)
                    if engagement_possible and not in_engagement:
                        return {
                            'valid': False,
                            'reason': 'Consolidate must end within engagement range of an enemy unit when possible'
                        }
                    if (not engagement_possible) and (not requires_engagement):
                        if _objective_fallback_ok():
                            return {'valid': True, 'reason': 'Valid final position (objective fallback)'}
                        if ignore_closest_enemy_requirement:
                            return {'valid': True, 'reason': 'Valid final position (Hearts Hardened to Duty)'}

                    from ..utility.aura_utils import distance_between_bases_3d
                    new_distance_to_unit = min(float(distance_between_bases_3d(new_base, em.model_base)) for em in closest_models)

                    if (not ignore_closest_enemy_requirement) and new_distance_to_unit >= closest_distance:
                        return {
                            'valid': False,
                            'reason': f'Consolidate must end closer to closest enemy unit ({closest_unit.name}): {new_distance_to_unit:.2f}" >= {closest_distance:.2f}"'
                        }

                    if validation_rules.get('prefer_base_contact', False) and not ignore_closest_enemy_requirement:
                        if closest_distance <= max_dist and new_distance_to_unit > BASE_CONTACT_EPSILON:
                            return {
                                'valid': False,
                                'reason': f'Consolidate must end in base contact with closest enemy unit ({closest_unit.name}) when possible'
                            }

                    return {'valid': True, 'reason': 'Valid final position'}

        if not use_unit:
            # Closest enemy model by edge-to-edge distance
            closest_enemy = None
            closest_distance = float('inf')
            for em in enemy_models:
                from ..utility.aura_utils import distance_between_bases_3d
                d = float(distance_between_bases_3d(current_base, em.model_base))
                if d < closest_distance:
                    closest_distance = d
                    closest_enemy = em

            if closest_enemy is not None:
                # If engagement range is achievable (based on distance), require ending in engagement range
                engagement_possible = closest_distance <= max_relevant_distance
                in_engagement = _is_in_engagement_range_of_any_enemy(enemy_models)
                if engagement_possible and not in_engagement:
                    return {
                        'valid': False,
                        'reason': 'Consolidate must end within engagement range of an enemy unit when possible'
                    }
                if (not engagement_possible) and (not requires_engagement):
                    if _objective_fallback_ok():
                        return {'valid': True, 'reason': 'Valid final position (objective fallback)'}
                    if ignore_closest_enemy_requirement:
                        return {'valid': True, 'reason': 'Valid final position (Hearts Hardened to Duty)'}

                # Must end closer to the closest enemy model (even if not reaching engagement)
                from ..utility.aura_utils import distance_between_bases_3d
                new_distance_to_closest = float(distance_between_bases_3d(new_base, closest_enemy.model_base))

                if (not ignore_closest_enemy_requirement) and new_distance_to_closest >= closest_distance:
                    return {
                        'valid': False,
                        'reason': f'Consolidate must end closer to closest enemy ({closest_enemy.name}): {new_distance_to_closest:.2f}" >= {closest_distance:.2f}"'
                    }

                # Prefer base contact if achievable within consolidate distance
                if validation_rules.get('prefer_base_contact', False) and not ignore_closest_enemy_requirement:
                    if closest_distance <= max_dist and new_distance_to_closest > BASE_CONTACT_EPSILON:
                        return {
                            'valid': False,
                            'reason': f'Consolidate must end in base contact with closest enemy ({closest_enemy.name}) when possible'
                        }

                # If we got here, consolidate is valid via enemy interaction
                return {'valid': True, 'reason': 'Valid final position'}

        return {
            'valid': False,
            'reason': 'Consolidate must end within engagement range of an enemy unit when possible'
        }

    # Check scout rules
    if validation_rules.get('min_distance_from_enemies', 0) > 0:
        min_distance = validation_rules['min_distance_from_enemies']
        # Create a temporary model base at the final position to check distance
        from ..utility.model_base import clone_base
        temp_base = clone_base(model.model_base)
        temp_base.set_position(position[0], position[1], position[2])

        for unit in game_map.units:
            if _units_share_army_identity(unit, model.parent_unit) or not unit.is_alive() or not unit.deployed:
                continue
            for enemy_model in unit.models:
                if not enemy_model.is_alive:
                    continue
                # Use edge-to-edge distance for accurate measurement
                from ..utility.aura_utils import distance_between_bases_3d
                distance = float(distance_between_bases_3d(temp_base, enemy_model.model_base))
                if distance < min_distance:
                    logger.debug(
                        "Scout validation - %s too close to %s (distance=%.2f, min_required=%.2f)",
                        getattr(model, "name", "?"),
                        getattr(enemy_model, "name", "?"),
                        distance,
                        min_distance,
                    )
                    return {'valid': False, 'reason': f'Scout movement must end {min_distance}" from enemies'}

    return {'valid': True, 'reason': 'Valid final position'}

def check_unit_coherency(unit: 'Unit') -> dict:
    """
    Check if a unit is in coherency using current model positions.

    Uses Warhammer 40k coherency rules:
    - 2" horizontal distance (base-to-base)
    - 5" vertical distance (base-to-base)

    Returns:
        dict: {'coherent': bool, 'reason': str, 'non_coherent_models': List[int]}
    """
    alive_indices = [i for i, m in enumerate(unit.models) if getattr(m, 'is_alive', True)]
    alive_count = len(alive_indices)

    if alive_count <= 1:
        return {'coherent': True, 'reason': 'Single model units are always coherent', 'non_coherent_models': []}

    required_neighbors = 2 if alive_count >= 7 else 1

    non_coherent_models: list[int] = []
    for i in alive_indices:
        neighbors = 0
        for j in alive_indices:
            if i == j:
                continue
            # model_base.coherency_distance() implements (<=2" horizontal AND <=5" vertical) as "0.0 means coherent"
            try:
                if unit.models[i].model_base.coherency_distance(unit.models[j].model_base) <= 0.0:
                    neighbors += 1
                    if neighbors >= required_neighbors:
                        break
            except Exception:
                continue
        if neighbors < required_neighbors:
            non_coherent_models.append(i)

    if non_coherent_models:
        return {
            'coherent': False,
            'reason': f'Models lack required coherency neighbors (alive={alive_count}, required_neighbors={required_neighbors})',
            'non_coherent_models': non_coherent_models
        }

    return {'coherent': True, 'reason': 'All alive models meet coherency neighbor requirements', 'non_coherent_models': []}

def validate_unit_coherency_after_movement(
    unit: 'Unit',
    new_positions: List[Tuple[float, float, float]],
    *,
    ignore_pending: bool = True,
) -> Tuple[bool, List[int]]:
    """
    Validate that unit coherency is maintained after model movement.
    
    This should be called after calculating paths for individual models to ensure
    the unit remains in coherency according to Warhammer 40k rules.
    
    Args:
        unit: The unit to validate
        new_positions: List of new positions (x, y, z) for each model
        
    Returns:
        Tuple[bool, List[int]]: (is_coherent, list_of_non_coherent_model_indices)
    """
    # Coherency is evaluated using 10th edition rules:
    # - Must be within 2" horizontally (base-to-base edge distance) AND within 5" vertically (base-to-base).
    # - For 2-6 models: each model must be within coherency of at least 1 other model.
    # - For 7+ models: each model must be within coherency of at least 2 other models.
    # - For 1 model: always coherent.

    alive_indices = [
        i for i, m in enumerate(unit.models)
        if getattr(m, 'is_alive', True) and (not ignore_pending or not getattr(m, "_pending_placement", False))
    ]
    alive_count = len(alive_indices)

    # Single-model units never need coherency checks
    if alive_count <= 1:
        return True, []

    # Map positions to model indices robustly (some callers pass only alive positions)
    positions_by_index: dict[int, Tuple[float, float, float]] = {}
    if len(new_positions) == len(unit.models):
        for i in alive_indices:
            pos = new_positions[i]
            positions_by_index[i] = (pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)
    elif len(new_positions) == alive_count:
        for k, i in enumerate(alive_indices):
            pos = new_positions[k]
            positions_by_index[i] = (pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)
    else:
        logger.warning(
            f"Coherency check: positions length ({len(new_positions)}) does not match unit models ({len(unit.models)}) "
            f"or alive models ({alive_count}) for unit {unit.name}"
        )
        return False, []

    required_neighbors = 2 if alive_count >= 7 else 1

    # Constants: coherency thresholds
    horiz_limit = 2.0
    vert_limit = 5.0

    non_coherent_models: list[int] = []

    # Count coherent neighbors for each alive model
    for i in alive_indices:
        model_i = unit.models[i]
        pos_i = positions_by_index[i]
        neighbors = 0

        # Temp base for accurate edge-to-edge horizontal measurement
        try:
            temp_base_i = model_i.model_base.__class__(model_i.model_base.base_type, model_i.model_base.radius)
            temp_base_i.set_position(pos_i[0], pos_i[1], pos_i[2])
            temp_base_i.set_facing(getattr(model_i.model_base, 'facing', 0.0))
            geom_i = temp_base_i.get_base_shape()
        except Exception:
            # If geometry can't be built, fail safe (treat as non-coherent)
            non_coherent_models.append(i)
            continue

        for j in alive_indices:
            if i == j:
                continue
            model_j = unit.models[j]
            pos_j = positions_by_index[j]

            # Vertical is base-to-base (not model top/bottom)
            vertical_dist = abs(float(pos_i[2]) - float(pos_j[2]))
            if vertical_dist > vert_limit + 1e-6:
                continue

            # Horizontal is base edge-to-edge on XY plane
            try:
                temp_base_j = model_j.model_base.__class__(model_j.model_base.base_type, model_j.model_base.radius)
                temp_base_j.set_position(pos_j[0], pos_j[1], pos_j[2])
                temp_base_j.set_facing(getattr(model_j.model_base, 'facing', 0.0))
                geom_j = temp_base_j.get_base_shape()
                horizontal_dist = geom_i.distance(geom_j)
            except Exception:
                continue

            if horizontal_dist <= horiz_limit + 1e-6:
                neighbors += 1
                if neighbors >= required_neighbors:
                    break

        if neighbors < required_neighbors:
            non_coherent_models.append(i)

    is_coherent = len(non_coherent_models) == 0
    logger.debug(
        f"Unit {unit.name} coherency check: {'PASS' if is_coherent else 'FAIL'} "
        f"(alive={alive_count}, required_neighbors={required_neighbors})"
    )
    if not is_coherent:
        logger.debug(f"Non-coherent models: {non_coherent_models}")

    return is_coherent, non_coherent_models

def process_unit_movement_with_coherency_check(unit: 'Unit', model_movements: List[Tuple[int, List[Tuple[float, float, float]]]]) -> Tuple[bool, List[int]]:
    """
    Process a complete unit movement with individual model paths and validate coherency.
    
    This function handles the complete workflow for human players moving models individually:
    1. Apply all model movements
    2. Validate unit coherency
    3. Return coherency status and any non-coherent models
    
    Args:
        unit: The unit being moved
        model_movements: List of (model_index, path) tuples for each model that moved
        
    Returns:
        Tuple[bool, List[int]]: (is_coherent, non_coherent_model_indices)
    """
    # Calculate final positions for all models
    final_positions = []
    
    for i, model in enumerate(unit.models):
        # Check if this model has a movement path
        moved = False
        for model_index, path in model_movements:
            if model_index == i:
                # Use the final position from the path
                final_positions.append(path[-1])
                moved = True
                break
        
        if not moved:
            # Model didn't move, use current position
            final_positions.append(model.position)
    
    # Validate coherency with the final positions
    is_coherent, non_coherent_models = validate_unit_coherency_after_movement(unit, final_positions)
    
    return is_coherent, non_coherent_models


def _resolve_ruins_floor_level(z_value: float, terrain_feature: 'TerrainFeature') -> tuple[Optional[int], Optional[dict]]:
    """Best-effort floor-level resolution for RUINS based on model Z and floor surfaces."""
    try:
        z = float(z_value)
    except (TypeError, ValueError):
        return None, None

    floors = getattr(terrain_feature, "floors", []) or []
    current_floor = None
    floor_level = None

    best_dist = float("inf")
    for floor in floors:
        if not isinstance(floor, dict):
            continue
        try:
            floor_elev = float(floor.get("elevation", 0.0) or 0.0)
        except (TypeError, ValueError):
            floor_elev = 0.0
        try:
            thickness = float(floor.get("thickness", RUINS_FLOOR_THICKNESS) or RUINS_FLOOR_THICKNESS)
        except (TypeError, ValueError):
            thickness = RUINS_FLOOR_THICKNESS
        surface = floor_elev + thickness
        dist = abs(z - surface)
        if dist < best_dist and dist < 1.0:
            best_dist = dist
            current_floor = floor
            floor_level = int(round(floor_elev / float(RUINS_FLOOR_HEIGHT)))

    if current_floor is None:
        if abs(z) < 1.0:
            floor_level = 0
            current_floor = {
                "polygon": getattr(terrain_feature, "footprint", None),
                "elevation": 0.0,
                "thickness": 0.0,
            }
        else:
            return None, None

    return floor_level, current_floor

def can_end_move_on_terrain(model: 'Model', terrain_feature: 'TerrainFeature') -> bool:
    """
    Check if a model can end its move on a specific terrain feature.

    Args:
        model: The model attempting to end its move
        obstacle: The terrain obstacle

    Returns:
        bool: True if the model can end its move on this terrain
    """
    from warhammer40k_ai.battlefield.map import TerrainType, RuinsTerrain
    terrain = terrain_feature.terrain_type
    base_overhang = base_overhangs_terrain(model, terrain_feature)
    unit = model.parent_unit

    if terrain == TerrainType.CRATER_AND_RUBBLE:
        return True  # Units can move over this terrain freely (can end move)
    elif terrain == TerrainType.BARRICADE_AND_FUEL_PIPES:
        return False  # Cannot be set up or end any kind of move on top of it
    elif terrain == TerrainType.DEBRIS_AND_STATUARY:
        return False  # Cannot be set up or end any kind of move on top of it
    elif terrain == TerrainType.HILLS_AND_SEALED_BUILDINGS:
        return not base_overhang  # Can end move if base does not overhang
    elif terrain == TerrainType.WOODS:
        return True  # Units can move over this terrain freely (can end move)
    elif terrain == TerrainType.RUINS:
        if not isinstance(terrain_feature, RuinsTerrain):
            return not base_overhang
        if unit is None:
            return False
        floor_level, current_floor = _resolve_ruins_floor_level(model.z, terrain_feature)
        if floor_level is None or current_floor is None:
            return False
        if floor_level == 0:
            return True

        can_access_val = getattr(unit, "can_access_upper_floors", None)
        can_access = bool(can_access_val() if callable(can_access_val) else can_access_val)
        if not can_access:
            return False

        floor_poly = current_floor.get("polygon") if isinstance(current_floor, dict) else None
        if floor_poly is not None:
            base_shape = model.model_base.get_base_shape_at(
                model.model_base.x,
                model.model_base.y,
                model.model_base.facing,
            )
            if hasattr(floor_poly, "covers"):
                within = floor_poly.covers(base_shape)
            else:
                within = floor_poly.contains(base_shape)
            if not within:
                return False
        return True
    else:
        # Default behavior for unknown terrain types
        return True

def base_overhangs_terrain(model: 'Model', terrain_feature: 'TerrainFeature') -> bool:
    """Check if a model's base overhangs the terrain feature."""
    base_shape = model.model_base.get_base_shape_at(model.model_base.x, model.model_base.y, model.model_base.facing)
    return not terrain_feature.footprint.contains(base_shape) and terrain_feature.footprint.intersects(base_shape)

def build_formation_templates(N, spacing):
    """
    Returns dict of {formation_name: np.ndarray[Nx2]} offsets.
    """
    templates = {}
    # BLOCK: fill rows of width = ceil(sqrt(N))
    w = int(np.ceil(np.sqrt(N)))
    coords = [(i % w, i // w) for i in range(N)]
    block = np.array(coords, dtype=float) * spacing
    # center
    block -= block.mean(axis=0)
    templates['block'] = block

    # WEDGE: triangular stacks
    wedge = []
    row = 0
    placed = 0
    while placed < N:
        for i in range(row+1):
            if placed >= N: break
            x = (i - row/2)*spacing
            y = -row*spacing
            wedge.append((x,y))
            placed += 1
        row += 1
    wedge = np.array(wedge)[:N]
    wedge -= wedge.mean(axis=0)
    templates['wedge'] = wedge

    # CIRCLE: petals around a circle
    angles = np.linspace(0, 2*np.pi, N, endpoint=False)
    circle = np.stack([np.cos(angles), np.sin(angles)], axis=1) * spacing
    templates['circle'] = circle

    # COLUMN: single file along +Y
    col = np.stack([np.zeros(N), np.arange(N)*spacing], axis=1)
    col -= col.mean(axis=0)
    templates['column'] = col

    return templates

def footprint_from_offsets(offsets, unit):
    """
    Given an (Nx2) offsets array and unit, reconstruct
    the convex-hull-buffer footprint Polygon.
    """
    polys = []
    # Get position from first alive model
    first_model = None
    for model in unit.models:
        if model.is_alive:
            first_model = model
            break

    if not first_model:
        return Polygon()  # Return empty polygon if no alive models

    cx, cy = first_model.get_location()[:2]
    for (dx,dy), m in zip(offsets, unit.models):
        base = m.model_base.get_base_shape()
        polys.append(translate(base, cx+dx - m.model_base.x,
                                cy+dy - m.model_base.y))
    hull = unary_union(polys).convex_hull
    # For deployment, use no buffer - just check actual model base collisions
    # Adding any buffer makes small units appear much larger than they are
    return hull

def build_spatial_index(obstacles, enemies):
    """
    Build an STRtree index of blocking polygons from terrain obstacles and enemy models.

    Parameters:
        obstacles: iterable of objects with a `.polygon` attribute (Shapely Polygon) or Shapely Polygon objects directly
        enemies: iterable of model objects with `.model_base.get_base_shape()` and `.is_alive()`.

    Returns:
        STRtree instance containing all blocker polygons.
    """
    blocker_polys = []
    # Add terrain obstacle polygons
    for obs in obstacles:
        # Handle both Obstacle objects (with .polygon attribute) and direct Polygon objects
        if hasattr(obs, 'polygon'):
            blocker_polys.append(obs.polygon)
        else:
            # Assume it's already a Shapely Polygon (e.g., boundary repulsors)
            blocker_polys.append(obs)

    # Add live enemy base shapes
    for enemy in enemies:
        if enemy.is_alive:
            blocker_polys.append(enemy.model_base.get_base_shape())

    # Build and return the spatial index
    return STRtree(blocker_polys)

def query_spatial_index(tree: STRtree, query_geom) -> List:
    """Query spatial index and return geometry objects (not indices)."""
    indices = tree.query(query_geom)
    if indices is None:
        return []
    try:
        if len(indices) == 0:
            return []
    except TypeError:
        return [tree.geometries[int(indices)]]
    return [tree.geometries[int(i)] for i in indices]
