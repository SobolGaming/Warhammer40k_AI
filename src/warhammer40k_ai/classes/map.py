from typing import List, Optional, Tuple, Dict, Any
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, convert_mm_to_inches, can_traverse_freely
from ..utility.constants import (
    ENGAGEMENT_RANGE_HORIZONTAL,
    ENGAGEMENT_RANGE_VERTICAL,
    RUINS_FLOOR_HEIGHT,
    RUINS_FLOOR_THICKNESS,
    RUINS_WALL_THICKNESS,
)
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
from shapely.affinity import scale, translate

from typing import TYPE_CHECKING, List, Tuple, Union
if TYPE_CHECKING:
    from .game import Game


class Map:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.boundary = self.create_boundary_polygon()
        self.terrain_features: List['TerrainFeature'] = []
        self.objectives = []
        self.deployment_zones = {}
        self.units = []
        self.occupied_positions = set()
        # UI hook (optional): set by GameView to allow combat code to request modals (e.g., PRECISION allocation)
        self.precision_allocation_provider = None
        # UI hooks (optional): set by GameView to allow core damage code to request allocation choices
        # Signature: provider(target_unit, eligible_models, ctx_dict) -> chosen_model | None
        self.damage_allocation_provider = None
        # Signature: provider(attacker_unit_root, eligible_models, ctx_dict) -> chosen_model | None
        self.hazardous_allocation_provider = None

    def create_boundary_polygon(self) -> Polygon:
        """
        Creates a Shapely Polygon representing the battlefield boundaries.
        """
        # Assuming the battlefield starts at (0, 0)
        vertices = [
            (0, 0),  # Bottom-left corner
            (self.width, 0),  # Bottom-right corner
            (self.width, self.height),  # Top-right corner
            (0, self.height),  # Top-left corner
        ]
        return Polygon(vertices)

    def add_terrain_feature(self, terrain_feature: 'TerrainFeature') -> None:
        """Add terrain feature."""
        self.terrain_features.append(terrain_feature)

    def add_terrain_features(self, terrain_features: List['TerrainFeature']) -> None:
        """Add multiple terrain features."""
        self.terrain_features.extend(terrain_features)

    @property
    def obstacles(self):
        """Legacy property for backward compatibility - returns terrain features."""
        return self.terrain_features

    def add_objective(self, objective: 'Objective') -> None:
        self.objectives.append(objective)

    def add_objectives(self, objectives: List['Objective']) -> None:
        self.objectives.extend(objectives)

    def get_objectives(self, is_secret: bool = False) -> List['Objective']:
        return [objective for objective in self.objectives if objective.category == ObjectiveCategory.SECRET]

    def place_unit(self, unit: Unit) -> bool:
        try:
            models = unit.get_models_for_collision()
        except Exception:
            models = unit.models
        for model in models:
            if not self.is_within_boundary(model):
                return False
            if self.check_collision_with_obstacles(model):
                return False
            if self.check_collision_with_other_friendly_units(model):
                return False
            if self.check_collision_with_other_enemy_units(model):
                return False
        self.units.append(unit)
        return True

    def get_all_models(self, units: Optional[List[Unit]] = None) -> List[Model] :
        if units is None:
            units = self.units
        all_models = []
        for unit in units:
            try:
                all_models.extend(unit.get_models_for_collision())
            except Exception:
                all_models.extend(unit.models)
        return all_models

    def get_enemy_units(self, unit: Unit) -> List[Unit]:
        enemy_units = []
        for test_unit in self.units:
            if unit.get_parent_army() != test_unit.get_parent_army():
                enemy_units.append(test_unit)
        return enemy_units

    def get_enemy_models(self, unit: Unit) -> List[Model]:
        enemy_models = []
        for test_unit in self.get_enemy_units(unit):
            try:
                enemy_models.extend(test_unit.get_models_for_collision())
            except Exception:
                enemy_models.extend(test_unit.models)
        return enemy_models

    def get_friendly_units(self, unit: Unit) -> List[Unit]:
        friendly_units = []
        for test_unit in self.units:
            if unit.get_parent_army() == test_unit.get_parent_army():
                friendly_units.append(test_unit)
        return friendly_units

    def get_friendly_models(self, unit: Unit) -> List[Model]:
        friendly_models = []
        for test_unit in self.get_friendly_units(unit):
            try:
                friendly_models.extend(test_unit.get_models_for_collision())
            except Exception:
                friendly_models.extend(test_unit.models)
        return friendly_models

    def is_within_boundary(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        """
        Checks if a given Shapely geometry is fully contained within the battlefield boundary.
        """
        test_shape = model.model_base.get_base_shape()
        if destination:
            test_shape = translate(test_shape, destination[0] - model.model_base.x, destination[1] - model.model_base.y)
        return self.boundary.contains(test_shape)

    def is_within_engagement_range(self, source_unit: Unit, target_unit: Unit) -> bool:
        """
        Check if any model in the source unit is within engagement range of any model in the target unit.

        Engagement Range in 10th Edition:
        - Within 1″ horizontally (measured base-to-base)
        - Within 5″ vertically

        Args:
            source_unit: The source unit to check from
            target_unit: The target unit to check against

        Returns:
            bool: True if any model in source unit is within engagement range of any model in target unit
        """
        # Attached units are treated as aggregates for rules purposes.
        source_models = source_unit.get_models_for_collision()
        target_models = target_unit.get_models_for_collision()

        for source_model in source_models:
            if not source_model.is_alive:
                continue
            for target_model in target_models:
                if not target_model.is_alive:
                    continue
                from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
                # Engagement Range is special-case:
                # - horizontal base-to-base in 2D
                # - vertical base-to-base separation (no model height)
                horizontal_distance = float(horizontal_distance_between_bases_2d(source_model.model_base, target_model.model_base))
                vertical_distance = float(vertical_distance_between_bases(source_model.model_base, target_model.model_base))

                # Check if within engagement range with debug output
                if (horizontal_distance <= ENGAGEMENT_RANGE_HORIZONTAL and
                    vertical_distance <= ENGAGEMENT_RANGE_VERTICAL):
                    source_pos = source_model.get_location()
                    target_pos = target_model.get_location()
                    print(f"🔍 DEBUG: ENGAGEMENT DETECTED!")
                    print(f"🔍 DEBUG: {source_unit.name} model at {source_pos}")
                    print(f"🔍 DEBUG: {target_unit.name} model at {target_pos}")
                    print(f"🔍 DEBUG: Horizontal distance: {horizontal_distance:.2f}\" (limit: {ENGAGEMENT_RANGE_HORIZONTAL}\")")
                    print(f"🔍 DEBUG: Vertical distance: {vertical_distance:.2f}\" (limit: {ENGAGEMENT_RANGE_VERTICAL}\")")
                    return True
        return False

    def calculate_pivot_cost(self, unit: Unit) -> float:
        """
        Calculate the pivot cost for a unit based on its characteristics.
        """
        if unit.is_aircraft:
            return 0
        if unit.is_monster or unit.is_vehicle:
            if not unit.has_circular_base or unit.base_size > convert_mm_to_inches(32 / 2):
                return 2
        if not unit.has_circular_base:
            return 1
        return 0

    def check_collision_with_obstacles(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        """Check collision with terrain features (legacy method name for backward compatibility)."""
        shape = model.model_base.get_base_shape()
        if destination:
            shape = translate(shape, destination[0] - model.model_base.x, destination[1] - model.model_base.y)

        # Check collision with terrain features using the new system
        from ..utility.calcs import get_terrain_blocking_polygons
        for terrain_feature in self.terrain_features:
            blocking_polygons = get_terrain_blocking_polygons(model.parent_unit, terrain_feature)
            for blocking_polygon in blocking_polygons:
                if shape.intersects(blocking_polygon):
                    return True
        return False

    def check_collision_with_other_friendly_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        for unit in self.get_friendly_units(model.parent_unit):
            if unit != model.parent_unit:  #  inter-unit collisions check done elsewhere
                for other_model in unit.models:
                    #print(f"Friendly Unit Check :: {model.parent_unit.name} checking collision with friendly units :: {other_model.parent_unit.name}")
                    if test_base.collides_with(other_model.model_base):
                        return True
        return False

    def check_collision_with_other_enemy_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        
        for unit in self.get_enemy_units(model.parent_unit):
            for other_model in unit.models:
                #print(f"Enemy Unit Check :: {model.parent_unit.name} checking collision with enemy units :: {other_model.parent_unit.name}")
                if test_base.collides_with(other_model.model_base):
                    return True
        return False

    ###########################################################################
    # Benefit of Cover (terrain-based save bonus)
    ###########################################################################
    def _sample_model_points_3d(self, model: Model, perimeter_points: int = 8, z_levels: int = 3) -> List[Tuple[float, float, float]]:
        """Sample points on a model's 3D volume for visibility tests."""
        base_shape = model.model_base.get_base_shape()
        exterior = base_shape.exterior

        perimeter_samples: List[Tuple[float, float]] = []
        if exterior.length > 0 and perimeter_points > 0:
            step = exterior.length / perimeter_points
            for i in range(perimeter_points):
                p = exterior.interpolate(step * i)
                perimeter_samples.append((p.x, p.y))

        centroid = base_shape.centroid
        xy_points = [(centroid.x, centroid.y)] + perimeter_samples

        z_bottom = model.model_base.z
        z_top = model.model_base.z + getattr(model.model_base, 'model_height', 2.0)
        if z_levels <= 1:
            z_samples = [z_bottom + 0.01]
        elif z_levels == 2:
            z_samples = [z_bottom + 0.01, z_top - 0.01]
        else:
            z_mid = (z_bottom + z_top) / 2.0
            z_samples = [z_bottom + 0.01, z_mid, z_top - 0.01]

        points_3d: List[Tuple[float, float, float]] = []
        for (x, y) in xy_points:
            for z in z_samples:
                points_3d.append((x, y, z))
        return points_3d

    def _segment_blocked_by_terrain_feature(
        self,
        p0: Tuple[float, float, float],
        p1: Tuple[float, float, float],
        terrain: 'TerrainFeature',
        shooter_model: Model,
        target_model: Model,
    ) -> bool:
        """Return True if the segment is blocked by *this* terrain feature."""
        line2d = LineString([(p0[0], p0[1]), (p1[0], p1[1])])
        if line2d.length == 0:
            return False

        def z_at_t(t: float) -> float:
            return p0[2] + t * (p1[2] - p0[2])

        footprint = getattr(terrain, 'footprint', None)
        if footprint is None:
            return False

        # RUINS special visibility rules (tournament-style)
        is_ruins = hasattr(terrain, 'walls') and hasattr(terrain, 'openings')
        if is_ruins:
            shooter_shape = shooter_model.model_base.get_base_shape()
            target_shape = target_model.model_base.get_base_shape()
            shooter_inside_any = footprint.intersects(shooter_shape)
            target_inside_any = footprint.intersects(target_shape)
            shooter_wholly_within = footprint.covers(shooter_shape)
            shooter_is_aircraft = False
            target_is_aircraft = False
            shooter_is_towering = False
            try:
                shooter_is_aircraft = bool(shooter_model.parent_unit.is_aircraft())
                target_is_aircraft = bool(target_model.parent_unit.is_aircraft())
                shooter_is_towering = bool(shooter_model.parent_unit.is_towering())
            except Exception:
                pass

            # Aircraft always use normal LOS: skip blanket ruins blocking.
            if not (shooter_is_aircraft or target_is_aircraft):
                # Outside-to-outside across footprint blocks.
                if not shooter_inside_any and not target_inside_any and line2d.intersects(footprint):
                    return True

                # Partially-inside (not wholly within) cannot see out unless towering.
                if shooter_inside_any and not shooter_wholly_within and not shooter_is_towering:
                    if not target_inside_any:
                        return True

        # Walls/openings handling (RUINS)
        walls = getattr(terrain, 'walls', None)
        openings = getattr(terrain, 'openings', None)
        if walls:
            for wall in walls:
                wall_poly = wall.get('polygon')
                if wall_poly is None:
                    continue
                if not line2d.intersects(wall_poly):
                    continue
                inter = line2d.intersection(wall_poly)
                if inter.is_empty:
                    continue
                if inter.geom_type == 'Point':
                    inter_pt = inter
                elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
                    inter_pt = inter.centroid
                else:
                    inter_pt = inter.representative_point()

                t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
                if t <= 1e-6 or t >= 1.0 - 1e-6:
                    continue
                z_here = z_at_t(t)
                z_bottom = wall.get('z_bottom', 0.0)
                z_top = wall.get('z_top', z_bottom)

                if z_bottom <= z_here <= z_top:
                    allowed = False
                    if openings:
                        for op in openings:
                            if not op.get('allows_los', False):
                                continue
                            op_poly = op.get('polygon')
                            if op_poly is None:
                                continue
                            if not op_poly.contains(inter_pt):
                                continue
                            if op.get('z_bottom', -1e9) <= z_here <= op.get('z_top', 1e9):
                                allowed = True
                                break
                    if not allowed:
                        return True
            return False

        # Generic terrain: footprint blocks within vertical span
        if not line2d.intersects(footprint):
            return False
        inter = line2d.intersection(footprint)
        if inter.is_empty:
            return False
        if inter.geom_type == 'Point':
            inter_pt = inter
        elif inter.geom_type in ('LineString', 'MultiPoint', 'MultiLineString'):
            inter_pt = inter.centroid
        else:
            inter_pt = inter.representative_point()
        t = line2d.project(inter_pt) / line2d.length if line2d.length > 0 else 0.0
        if t <= 1e-6 or t >= 1.0 - 1e-6:
            return False
        z_here = z_at_t(t)

        min_z, max_z = 0.0, 0.0
        if hasattr(terrain, 'height'):
            min_z, max_z = 0.0, float(getattr(terrain, 'height'))
        elif hasattr(terrain, 'rim_height'):
            min_z, max_z = 0.0, float(getattr(terrain, 'rim_height'))
        elif hasattr(terrain, 'bounding_box') and isinstance(terrain.bounding_box, dict):
            try:
                min_z = float(terrain.bounding_box.get('min', (0, 0, 0))[2])
                max_z = float(terrain.bounding_box.get('max', (0, 0, 0))[2])
            except Exception:
                min_z, max_z = 0.0, 2.0
        else:
            max_z = 2.0

        return min_z <= z_here <= max_z

    def _is_fully_visible_due_to_terrain(self, shooter_model: Model, target_model: Model, terrain: 'TerrainFeature') -> bool:
        """True iff every sampled point on target is visible to shooter w.r.t this terrain."""
        shooter_points = self._sample_model_points_3d(shooter_model, perimeter_points=8, z_levels=3)
        target_points = self._sample_model_points_3d(target_model, perimeter_points=8, z_levels=3)

        for tp in target_points:
            any_visible = False
            for sp in shooter_points:
                if not self._segment_blocked_by_terrain_feature(sp, tp, terrain, shooter_model, target_model):
                    any_visible = True
                    break
            if not any_visible:
                return False
        return True

    def can_model_see_model(self, shooter_model: Model, target_model: Model) -> bool:
        """
        Best-effort line-of-sight check for visibility requirements (e.g. PRECISION).

        Returns True if there exists at least one sampled point on the target that is not blocked
        from at least one sampled point on the shooter by any terrain feature.
        """
        try:
            shooter_points = self._sample_model_points_3d(shooter_model, perimeter_points=6, z_levels=2)
            target_points = self._sample_model_points_3d(target_model, perimeter_points=6, z_levels=2)
        except Exception:
            return True

        terrain_features = list(getattr(self, "terrain_features", []) or [])
        for tp in target_points:
            for sp in shooter_points:
                blocked = False
                for terrain in terrain_features:
                    try:
                        if self._segment_blocked_by_terrain_feature(sp, tp, terrain, shooter_model, target_model):
                            blocked = True
                            break
                    except Exception:
                        continue
                if not blocked:
                    return True
        return False

    def get_benefit_of_cover_for_ranged_attack(
        self,
        attacking_unit: Unit,
        target_model: Model,
        weapon_profile: Optional[Any] = None,
        ap: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Evaluate Benefit of Cover for RUINS/WOODS for a single ranged attack allocation.

        RUINS & WOODS:
        - If target_model is wholly within the terrain feature, OR
        - If target_model is not fully visible to every model in attacking_unit because of that terrain feature,
          then target_model has Benefit of Cover against that attack.

        TODO: Extend this method to support other terrain types (Crater, Barricade, etc.).
        """
        result: Dict[str, Any] = {
            "has_benefit_of_cover": False,
            "source_terrain_type": None,
            "reason": None,
        }

        # If weapon ignores cover, it cancels Benefit of Cover.
        try:
            if weapon_profile is not None:
                parent_wg = getattr(weapon_profile, "parent_wargear", None)
                if parent_wg is not None and hasattr(parent_wg, "is_ignores_cover") and parent_wg.is_ignores_cover():
                    return result
        except Exception:
            pass

        # Evaluate per terrain feature. Multiple instances are not cumulative, so we early-return on first match.
        for terrain in getattr(self, "terrain_features", []):
            ttype = getattr(terrain, "terrain_type", None)
            if ttype not in (TerrainType.RUINS, TerrainType.WOODS):
                continue

            footprint = getattr(terrain, "footprint", None)
            if footprint is None:
                continue

            # Wholly within (2D footprint-based: base wholly within footprint)
            try:
                base_shape = target_model.model_base.get_base_shape()
                if footprint.covers(base_shape):
                    result["has_benefit_of_cover"] = True
                    result["source_terrain_type"] = getattr(ttype, "name", str(ttype))
                    result["reason"] = "Target model wholly within terrain feature"
                    return result
            except Exception:
                pass

            # Not fully visible to every model in the attacking unit because of this terrain feature.
            for attacker_model in getattr(attacking_unit, "models", []):
                if not getattr(attacker_model, "is_alive", False):
                    continue
                try:
                    fully_visible = self._is_fully_visible_due_to_terrain(attacker_model, target_model, terrain)
                except Exception:
                    fully_visible = True
                if not fully_visible:
                    result["has_benefit_of_cover"] = True
                    result["source_terrain_type"] = getattr(ttype, "name", str(ttype))
                    result["reason"] = f"Not fully visible to {getattr(attacker_model, 'name', 'an attacker model')} due to terrain"
                    return result

        return result

    def get_height_at_point(self, x: float, y: float) -> float:
        """
        Check if a given X,Y coordinate has terrain and return its height (Z coordinate).
        If multiple terrain features overlap, return the maximum height.

        Args:
            x (float): X coordinate to check
            y (float): Y coordinate to check

        Returns:
            float: Maximum height of terrain at the given point, or 0 if no terrain is present
        """
        point = Point(x, y)
        max_height = 0.0

        for terrain_feature in self.terrain_features:
            if terrain_feature.footprint.contains(point):
                # RUINS: compute floor surface height properly (prefer the lowest floor that contains XY)
                if getattr(terrain_feature, 'terrain_type', None) == TerrainType.RUINS and hasattr(terrain_feature, 'floors'):
                    try:
                        candidate_surfaces = []
                        for fl in getattr(terrain_feature, 'floors', []) or []:
                            poly = fl.get('polygon')
                            if poly is not None and poly.contains(point):
                                elev = fl.get('elevation', 0.0)
                                thickness = fl.get('thickness', RUINS_FLOOR_THICKNESS)
                                candidate_surfaces.append(elev + thickness)
                        if candidate_surfaces:
                            # Choose the lowest surface (ground first if present)
                            surface_z = min(candidate_surfaces)
                            max_height = max(max_height, surface_z)
                            continue
                        else:
                            # Inside RUINS footprint but no explicit floor polygon match; assume ground floor top thickness
                            max_height = max(max_height, RUINS_FLOOR_THICKNESS)
                            continue
                    except Exception:
                        # Fall through to generic handling if something goes wrong
                        pass

                # Generic terrain handling
                if hasattr(terrain_feature, 'height'):
                    max_height = max(max_height, terrain_feature.height)
                elif hasattr(terrain_feature, 'rim_height'):
                    max_height = max(max_height, terrain_feature.rim_height)
                else:
                    # Default minimal ground height
                    max_height = max(max_height, 0.0)

        return max_height

    def get_distance_between_units(self, unit1: Unit, unit2: Unit) -> float:
        """Calculate the shortest distance between two units.
        
        Args:
            unit1 (Unit): First unit
            unit2 (Unit): Second unit
            
        Returns:
            float: The shortest distance between any models in the two units
        """
        from ..utility.aura_utils import min_distance_between_units_3d
        return float(min_distance_between_units_3d(unit1, unit2, use_attached_aggregate=True))

    def is_path_blocked(self, unit: Unit, target: Unit) -> bool:
        """Check if there's a clear path between two units considering terrain and obstacles.

        Args:
            unit (Unit): The unit checking the path
            target (Unit): The target unit

        Returns:
            bool: True if path is blocked, False if clear
        """
        # Get the positions from first alive model in each unit
        unit_pos = None
        try:
            unit_models = unit.get_models_for_collision()
        except Exception:
            unit_models = unit.models
        for model in unit_models:
            if model.is_alive:
                unit_pos = model.get_location()
                break

        target_pos = None
        try:
            target_models = target.get_models_for_collision()
        except Exception:
            target_models = target.models
        for model in target_models:
            if model.is_alive:
                target_pos = model.get_location()
                break

        if not unit_pos or not target_pos:
            return True  # Consider path blocked if we can't determine positions

        # Create a line representing the path
        path = LineString([(unit_pos[0], unit_pos[1]), (target_pos[0], target_pos[1])])

        # Check for intersections with terrain features
        for terrain_feature in self.terrain_features:
            if path.intersects(terrain_feature.footprint):
                if not can_traverse_freely(unit, terrain_feature):
                    return True  # Path is blocked

        return False  # Path is clear

    def get_battlefield_edge_repulsors(self) -> List:
        """Generate battlefield edge repulsors for movement collision detection.
        
        Returns:
            List of Shapely polygons representing battlefield edge repulsors
        """
        from shapely.geometry import Polygon
        
        repulsors = []
        repulsor_thickness = 0.5  # 0.5 inch thick repulsor zones
        
        # Left battlefield edge repulsor
        left_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (0, -repulsor_thickness),
            (0, self.height + repulsor_thickness),
            (-repulsor_thickness, self.height + repulsor_thickness)
        ])
        repulsors.append(left_edge)
        
        # Right battlefield edge repulsor
        right_edge = Polygon([
            (self.width, -repulsor_thickness),
            (self.width + repulsor_thickness, -repulsor_thickness),
            (self.width + repulsor_thickness, self.height + repulsor_thickness),
            (self.width, self.height + repulsor_thickness)
        ])
        repulsors.append(right_edge)
        
        # Bottom battlefield edge repulsor
        bottom_edge = Polygon([
            (-repulsor_thickness, -repulsor_thickness),
            (self.width + repulsor_thickness, -repulsor_thickness),
            (self.width + repulsor_thickness, 0),
            (-repulsor_thickness, 0)
        ])
        repulsors.append(bottom_edge)
        
        # Top battlefield edge repulsor
        top_edge = Polygon([
            (-repulsor_thickness, self.height),
            (self.width + repulsor_thickness, self.height),
            (self.width + repulsor_thickness, self.height + repulsor_thickness),
            (-repulsor_thickness, self.height + repulsor_thickness)
        ])
        repulsors.append(top_edge)
        
        return repulsors


class TerrainType(Enum):
    """Types of terrain features."""
    CRATER_AND_RUBBLE = auto()
    BARRICADE_AND_FUEL_PIPES = auto()
    DEBRIS_AND_STATUARY = auto()
    HILLS_AND_SEALED_BUILDINGS = auto()
    WOODS = auto()
    RUINS = auto()


class TerrainFeature:
    """Base class for all terrain features using polygon-based approach."""

    def __init__(self, terrain_type: TerrainType, footprint: Polygon,
                 bounding_box: dict, traversal_rules: dict = None):
        """
        Args:
            terrain_type: Type of terrain
            footprint: 2D ground outline of the terrain
            bounding_box: 3D bounding box for spatial indexing
            traversal_rules: Rules for which units can traverse this terrain
        """
        self.terrain_type = terrain_type
        self.footprint = footprint
        self.bounding_box = bounding_box
        self.traversal_rules = traversal_rules or {}

    def point_in_bounds(self, position: Tuple[float, float, float]) -> bool:
        """Check if a 3D position is within the terrain's bounding box."""
        x, y, z = position
        min_x, min_y, min_z = self.bounding_box["min"]
        max_x, max_y, max_z = self.bounding_box["max"]
        return (min_x <= x <= max_x and
                min_y <= y <= max_y and
                min_z <= z <= max_z)

    def can_unit_traverse(self, unit) -> bool:
        """Check if a unit can traverse this terrain. Override in subclasses."""
        return True

class RuinsTerrain(TerrainFeature):
    """RUINS terrain with walls, floors, and openings."""

    def __init__(self, footprint: Polygon, walls: List[dict] = None,
                 openings: List[dict] = None, floors: List[dict] = None,
                 height_map: dict = None):
        """
        Args:
            footprint: 2D ground outline of the ruins
            walls: List of wall definitions with polygon, z_bottom, z_top, thickness
            openings: List of opening definitions (windows/doors)
            floors: List of floor definitions with polygon and elevation
            height_map: Optional detailed elevation map {(x,y): z}
        """
        self.walls = walls or []
        self.openings = openings or []
        self.floors = floors or []
        self.height_map = height_map or {}

        # Calculate bounding box
        bounds = footprint.bounds  # (minx, miny, maxx, maxy)
        max_z = max([wall["z_top"] for wall in self.walls] +
                   [floor["elevation"] + floor.get("thickness", 0.5) for floor in self.floors] + [0.0])

        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], max_z)
        }

        # Traversal rules for RUINS
        traversal_rules = {
            "infantry_can_pass_walls": True,
            "beast_can_pass_walls": True,
            "vehicle_can_pass_walls": False,
            "monster_can_pass_walls": False,
            "flying_can_pass_walls": True,
            "titanic_can_pass_walls": False,
        }

        super().__init__(TerrainType.RUINS, footprint, bounding_box, traversal_rules)

    def check_wall_collision(self, position: Tuple[float, float, float]) -> bool:
        """Check if a position collides with any wall."""
        if not self.point_in_bounds(position):
            return False

        x, y, z = position
        point = Point(x, y)

        for wall in self.walls:
            if (wall["z_bottom"] <= z <= wall["z_top"] and
                wall["polygon"].contains(point)):
                return True
        return False

    def check_opening_passage(self, position: Tuple[float, float, float]) -> bool:
        """Check if a position is within an opening that allows movement."""
        x, y, z = position
        point = Point(x, y)

        for opening in self.openings:
            if (opening.get("allows_movement", False) and
                opening["z_bottom"] <= z <= opening["z_top"] and
                opening["polygon"].contains(point)):
                return True
        return False

    def can_unit_move_through(self, unit, position: Tuple[float, float, float]) -> bool:
        """Check if a unit can move through a specific position in the ruins."""
        # Flying units can pass through anything
        if getattr(unit, 'is_flying', False):
            return True

        # Check wall collision
        if self.check_wall_collision(position):
            # Check if unit can pass through walls
            unit_type = self._get_unit_type(unit)
            if not self.traversal_rules.get(f"{unit_type}_can_pass_walls", False):
                # Check for openings that allow movement
                if not self.check_opening_passage(position):
                    return False

        return True

    def _get_unit_type(self, unit) -> str:
        """Get unit type string for traversal rule lookup."""
        if getattr(unit, 'is_infantry', False):
            return "infantry"
        elif getattr(unit, 'is_beast', False):
            return "beast"
        elif getattr(unit, 'is_flying', False):
            return "flying"
        elif getattr(unit, 'is_titanic', False):
            return "titanic"
        elif 'Vehicle' in getattr(unit, 'keywords', []):
            return "vehicle"
        elif 'Monster' in getattr(unit, 'keywords', []):
            return "monster"
        else:
            return "infantry"  # Default to infantry rules

class WoodsTerrain(TerrainFeature):
    """WOODS terrain - all units can traverse freely."""

    def __init__(self, footprint: Polygon, height: float = 6.0, density: float = 0.7):
        """
        Args:
            footprint: 2D outline of the woods
            height: Height of the tree canopy
            density: Tree density (0.0 to 1.0) affects line of sight
        """
        self.height = height
        self.density = density

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "blocks_line_of_sight": density > 0.5,
            "provides_cover": True
        }

        super().__init__(TerrainType.WOODS, footprint, bounding_box, traversal_rules)

class CraterTerrain(TerrainFeature):
    """CRATER_AND_RUBBLE terrain - difficult ground, all units can traverse."""

    def __init__(self, footprint: Polygon, depth: float = 2.0, rim_height: float = 1.0):
        """
        Args:
            footprint: 2D outline of the crater
            depth: How deep the crater goes (negative Z)
            rim_height: Height of crater rim above ground
        """
        self.depth = depth
        self.rim_height = rim_height

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], -depth),
            "max": (bounds[2], bounds[3], rim_height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "difficult_terrain": True,
            "provides_cover": True
        }

        super().__init__(TerrainType.CRATER_AND_RUBBLE, footprint, bounding_box, traversal_rules)

class BarricadeTerrain(TerrainFeature):
    """BARRICADE_AND_FUEL_PIPES terrain - linear obstacles that can be climbed over."""

    def __init__(self, footprint: Polygon, height: float = 3.0, thickness: float = 1.0):
        """
        Args:
            footprint: 2D outline of the barricade
            height: Height of the barricade
            thickness: Thickness of the barricade structure
        """
        self.height = height
        self.thickness = thickness

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "requires_climbing": height > 2.0,
            "provides_cover": True,
            "blocks_vehicles": height > 4.0  # Very tall barricades block vehicles
        }

        super().__init__(TerrainType.BARRICADE_AND_FUEL_PIPES, footprint, bounding_box, traversal_rules)

class DebrisTerrain(TerrainFeature):
    """DEBRIS_AND_STATUARY terrain - scattered obstacles, can traverse but not end on."""

    def __init__(self, footprint: Polygon, height: float = 2.0, scatter_density: float = 0.6):
        """
        Args:
            footprint: 2D outline of the debris field
            height: Average height of debris pieces
            scatter_density: How densely packed the debris is
        """
        self.height = height
        self.scatter_density = scatter_density

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "cannot_end_move_on": True,  # Can move through but not stop on
            "difficult_terrain": scatter_density > 0.5,
            "provides_cover": True
        }

        super().__init__(TerrainType.DEBRIS_AND_STATUARY, footprint, bounding_box, traversal_rules)

class HillsBuildingsTerrain(TerrainFeature):
    """HILLS_AND_SEALED_BUILDINGS terrain - elevated surfaces with access restrictions."""

    def __init__(self, footprint: Polygon, height: float = 6.0,
                 access_points: List[Polygon] = None, max_base_size: float = 3.0):
        """
        Args:
            footprint: 2D outline of the hill/building
            height: Height of the elevated surface
            access_points: Areas where units can climb up (ramps, stairs)
            max_base_size: Maximum base size that can fit without overhanging
        """
        self.height = height
        self.access_points = access_points or []
        self.max_base_size = max_base_size

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "requires_access_point": len(self.access_points) > 0,
            "base_overhang_check": True,
            "max_base_size": max_base_size,
            "provides_elevation_advantage": True
        }

        super().__init__(TerrainType.HILLS_AND_SEALED_BUILDINGS, footprint, bounding_box, traversal_rules)

    def can_base_fit(self, base_size: float) -> bool:
        """Check if a model's base can fit on this terrain without overhanging."""
        return base_size <= self.max_base_size

    def has_access_from(self, position: Tuple[float, float]) -> bool:
        """Check if there's an access point near the given position."""
        if not self.access_points:
            return True  # No restrictions if no access points defined

        point = Point(position[0], position[1])
        return any(access.contains(point) or access.distance(point) < 2.0
                  for access in self.access_points)

class TerrainFactory:
    """Factory class for creating terrain features."""

    @staticmethod
    def create_ruins(footprint_vertices: List[Tuple[float, float]],
                    wall_height: float = RUINS_FLOOR_HEIGHT, num_floors: int = 1,
                    has_windows: bool = True, has_doors: bool = True) -> RuinsTerrain:
        """Create a RUINS terrain with walls, floors, and openings."""
        footprint = Polygon(footprint_vertices)

        walls = []
        openings = []
        floors = []

        # Create floors for each level
        for floor_level in range(num_floors + 1):  # Include ground floor
            floors.append({
                "polygon": footprint,
                "elevation": floor_level * wall_height,
                "thickness": RUINS_FLOOR_THICKNESS
            })

        # Create walls around perimeter
        coords = list(footprint.exterior.coords)[:-1]  # Remove duplicate last point
        for i in range(len(coords)):
            start_point = coords[i]
            end_point = coords[(i + 1) % len(coords)]

            # Create wall segment with thickness
            wall_line = LineString([start_point, end_point])
            wall_polygon = wall_line.buffer(RUINS_WALL_THICKNESS / 2.0)

            for floor_level in range(num_floors + 1):
                walls.append({
                    "polygon": wall_polygon,
                    "z_bottom": floor_level * wall_height,
                    "z_top": (floor_level + 1) * wall_height,
                    "thickness": RUINS_WALL_THICKNESS
                })

                # Add windows and doors
                if has_windows and floor_level > 0:  # Windows on upper floors
                    window_polygon = wall_line.interpolate(0.5, normalized=True).buffer(1.0)
                    openings.append({
                        "polygon": window_polygon,
                        "z_bottom": floor_level * wall_height + 1.0,
                        "z_top": floor_level * wall_height + 3.0,
                        "allows_movement": False,
                        "allows_los": True
                    })

                if has_doors and floor_level == 0 and i == 0:  # Door on ground floor, first wall
                    door_polygon = wall_line.interpolate(0.5, normalized=True).buffer(1.5)
                    openings.append({
                        "polygon": door_polygon,
                        "z_bottom": 0.0,
                        "z_top": 3.0,
                        "allows_movement": True,
                        "allows_los": True
                    })

        return RuinsTerrain(footprint, walls, openings, floors)

    @staticmethod
    def create_woods(footprint_vertices: List[Tuple[float, float]],
                    height: float = 6.0, density: float = 0.7) -> WoodsTerrain:
        """Create WOODS terrain."""
        footprint = Polygon(footprint_vertices)
        return WoodsTerrain(footprint, height, density)

    @staticmethod
    def create_crater(footprint_vertices: List[Tuple[float, float]],
                     depth: float = 2.0, rim_height: float = 1.0) -> CraterTerrain:
        """Create CRATER_AND_RUBBLE terrain."""
        footprint = Polygon(footprint_vertices)
        return CraterTerrain(footprint, depth, rim_height)

    @staticmethod
    def create_barricade(start_point: Tuple[float, float], end_point: Tuple[float, float],
                        height: float = 3.0, thickness: float = 1.0) -> BarricadeTerrain:
        """Create BARRICADE_AND_FUEL_PIPES terrain."""
        line = LineString([start_point, end_point])
        footprint = line.buffer(thickness / 2.0)
        return BarricadeTerrain(footprint, height, thickness)

    @staticmethod
    def create_debris(footprint_vertices: List[Tuple[float, float]],
                     height: float = 2.0, density: float = 0.6) -> DebrisTerrain:
        """Create DEBRIS_AND_STATUARY terrain."""
        footprint = Polygon(footprint_vertices)
        return DebrisTerrain(footprint, height, density)

    @staticmethod
    def create_hill(footprint_vertices: List[Tuple[float, float]],
                   height: float = 6.0, access_points: List[List[Tuple[float, float]]] = None,
                   max_base_size: float = 3.0) -> HillsBuildingsTerrain:
        """Create HILLS_AND_SEALED_BUILDINGS terrain."""
        footprint = Polygon(footprint_vertices)
        access_polygons = []
        if access_points:
            access_polygons = [Polygon(points) for points in access_points]
        return HillsBuildingsTerrain(footprint, height, access_polygons, max_base_size)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant1() -> RuinsTerrain:
        """Create a preset RUINS terrain piece (12" x 6") matching the specified layout.

        Details:
        - Footprint: 12" x 6" rectangle
        - Wall thickness: 0.5"
        - Walls flush to the bottom long edge (y=0) with adjusted spans:
          • Long wall: inset 2" from each side (x=2..10) along y=0, on all levels
          • Short walls: moved in to meet the long wall ends, at x=2 and x=10; 4" long (y=0..4) on all levels
        - Ground floor (level 0): 4" wall height, no windows
        - First floor (level 1): 4" wall height, windows
          • Long wall: two 2" windows (shorter wall span), at x=[3-5], [7-9]
          • Short walls: one 2" window each, spanning y=[2-4]
          • All windows 1"-3" above that floor (allows LOS only)
        - Second floor (level 2): 1" parapets, no windows
        - No doors
        """
        # Footprint polygon
        footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        # Define core wall line segments
        # Center wall lines are inset by 0.25" from footprint edges so buffered walls stay within footprint
        # Long wall is inset by 2" from each short edge (x=2..10) -> centerline x=2.25..9.75
        long_wall_line = LineString([(2.25, 0.25), (9.75, 0.25)])
        # Short walls are 4" long and meet the long wall at x=2 and x=10.
        # Use inset centerlines so buffered walls stay within footprint.
        short_wall_left_line_upper = LineString([(2.0 + half_t, 0.25), (2.0 + half_t, 3.75)])
        short_wall_right_line_upper = LineString([(10.0 - half_t, 0.25), (10.0 - half_t, 3.75)])
        # Ground floor short walls are also 4" long now
        short_wall_left_line_ground = short_wall_left_line_upper
        short_wall_right_line_ground = short_wall_right_line_upper

        # Buffer to thickness to create polygons
        long_wall_poly = long_wall_line.buffer(half_t)
        short_wall_left_poly_upper = short_wall_left_line_upper.buffer(half_t)
        short_wall_right_poly_upper = short_wall_right_line_upper.buffer(half_t)
        short_wall_left_poly_ground = short_wall_left_line_ground.buffer(half_t)
        short_wall_right_poly_ground = short_wall_right_line_ground.buffer(half_t)

        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness
            })

        # Ground floor walls (no windows), height equals floor height; short walls extend full 6" length
        add_wall(long_wall_poly, floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(short_wall_left_poly_ground, floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(short_wall_right_poly_ground, floor_level=0, height=RUINS_FLOOR_HEIGHT)

        # First floor walls (with windows), height equals floor height; short walls are 4" long
        add_wall(long_wall_poly, floor_level=1, height=RUINS_FLOOR_HEIGHT)
        add_wall(short_wall_left_poly_upper, floor_level=1, height=RUINS_FLOOR_HEIGHT)
        add_wall(short_wall_right_poly_upper, floor_level=1, height=RUINS_FLOOR_HEIGHT)

        # Windows on first floor: keep within a 3" wall height (0.75"-2.25" above floor)
        z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
        z1_top = 2.25 + RUINS_FLOOR_HEIGHT

        # Long wall: two 2" windows within the shortened span x=2..10
        for x_start, x_end in [(3.0, 5.0), (7.0, 9.0)]:
            openings.append({
                # Align with long wall thickness at y = 0.25 ± 0.25
                "polygon": box(x_start, 0.25 - half_t, x_end, 0.25 + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True
            })

        # Short wall windows: y from 1" to 3", centered on x=2 and x=10 walls
        openings.append({
            "polygon": box((2.0 + half_t) - half_t, 1.0, (2.0 + half_t) + half_t, 3.0),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True
        })
        openings.append({
            "polygon": box((10.0 - half_t) - half_t, 1.0, (10.0 - half_t) + half_t, 3.0),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True
        })

        # Second floor walls (parapets), height 1"; short walls are 4" long
        add_wall(long_wall_poly, floor_level=2, height=1.0)
        add_wall(short_wall_left_poly_upper, floor_level=2, height=1.0)
        add_wall(short_wall_right_poly_upper, floor_level=2, height=1.0)

        # Floors: ground (0) uses full footprint; upper floors are narrowed to match long-wall span.
        # Upper floors extend to y=4 and x=2..10 (aligned with the inset long wall).
        upper_floor_poly = box(2.0, 0.0, 10.0, 4.0)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS
        })
        floors.append({
            "polygon": upper_floor_poly,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS
        })
        floors.append({
            "polygon": upper_floor_poly,
            "elevation": RUINS_FLOOR_HEIGHT * 2.0,
            "thickness": RUINS_FLOOR_THICKNESS
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant2() -> RuinsTerrain:
        """Create RUINS preset (12" x 6") Variant 2 - mirror of Variant 3 (top-right corner).

        Connecting corner: top-right (12,6)
        - Top long-edge wall (y=6), measured leftwards from the connecting corner:
          • Ground: 8" span (x=4..12)
          • 1st:    8" span (x=4..12)
          • 2nd:    6" span (x=6..12)  (parapet, 1" tall)
        - Right short-edge wall (x=12), measured downwards from the connecting corner:
          • Ground: 4" span (y=2..6)
          • 1st:    3" span (y=3..6)
          • 2nd:    2" span (y=4..6)  (parapet, 1" tall)

        Windows/doors:
        - Ground floor: none
        - 1st: windows (LOS-only) mirrored from Variant 3
        - 2nd: none (parapet)

        Floors (triangular, matching wall legs):
        - Ground: full 12x6 footprint
        - 1st: right triangle with legs 8 (x) and 3 (y), right angle at (12,6)
        - 2nd: right triangle with legs 6 (x) and 2 (y), right angle at (12,6)
        """

        # Footprint polygon
        footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness
            })

        # Centerlines inset so buffered walls remain within footprint
        y_top_cl = 6.0 - half_t  # 5.75
        x_right_cl = 12.0 - half_t  # 11.75

        # Top wall spans (measured left from x=12): ground/l1 are 8", l2 is 6" parapet
        top_line_g = LineString([(4.0 + half_t, y_top_cl), (12.0 - half_t, y_top_cl)])
        top_line_l1 = LineString([(4.0 + half_t, y_top_cl), (12.0 - half_t, y_top_cl)])
        top_line_l2 = LineString([(6.0 + half_t, y_top_cl), (12.0 - half_t, y_top_cl)])

        # Right wall spans (measured down from y=6): ground 4", l1 3", l2 2" parapet
        right_line_g = LineString([(x_right_cl, 2.0 + half_t), (x_right_cl, 6.0 - half_t)])
        right_line_l1 = LineString([(x_right_cl, 3.0 + half_t), (x_right_cl, 6.0 - half_t)])
        right_line_l2 = LineString([(x_right_cl, 4.0 + half_t), (x_right_cl, 6.0 - half_t)])

        # Ground + first floors are full-height walls
        add_wall(top_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(right_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(top_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
        add_wall(right_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)

        # Second floor is parapet (1")
        add_wall(top_line_l2.buffer(half_t), floor_level=2, height=1.0)
        add_wall(right_line_l2.buffer(half_t), floor_level=2, height=1.0)

        # Windows (LOS only): keep within a 3" wall height (0.75"-2.25" above floor)
        z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
        z1_top = 2.25 + RUINS_FLOOR_HEIGHT

        # First floor windows
        # Top wall span x=4..12: two 2" windows (mirrored from Variant 3)
        for x_start, x_end in [(6.0, 8.0), (9.0, 11.0)]:
            openings.append({
                "polygon": box(x_start, y_top_cl - half_t, x_end, y_top_cl + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True
            })
        # Right wall span y=3..6: one vertical window centered in span (mirrored)
        openings.append({
            "polygon": box(x_right_cl - half_t, 3.5, x_right_cl + half_t, 5.5),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True
        })

        # Floors
        # Ground: full footprint
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS
        })
        # First floor: right triangle legs 8 (x) and 3 (y), right angle at (12,6)
        floor1 = Polygon([(12.0, 6.0), (4.0, 6.0), (12.0, 3.0)])
        floors.append({
            "polygon": floor1,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS
        })
        # Second floor: right triangle legs 6 (x) and 2 (y), right angle at (12,6)
        floor2 = Polygon([(12.0, 6.0), (6.0, 6.0), (12.0, 4.0)])
        floors.append({
            "polygon": floor2,
            "elevation": RUINS_FLOOR_HEIGHT * 2.0,
            "thickness": RUINS_FLOOR_THICKNESS
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant3() -> RuinsTerrain:
        """Create RUINS preset (12" x 6") Variant 3 - adjusted reverse-L wall spans.

        This is similar in intent to the old Variant 3 (a mirror of Variant 2), but with
        corrected wall spans relative to the connecting corner between the long wall and
        the short wall.

        Connecting corner: top-left (0,6)
        - Top long-edge wall (y=6):
          • Ground: 8" span from the connecting corner (x=0..8)
          • 1st:    8" span from the connecting corner (x=0..8)
          • 2nd:    6" span from the connecting corner (x=0..6)  (parapet)
        - Left short-edge wall (x=0), measured down from the connecting corner:
          • Ground: 4" span (y=2..6)
          • 1st:    3" span (y=3..6)
          • 2nd:    2" span (y=4..6)  (parapet)

        Windows/doors:
        - Ground floor: none
        - 1st/2nd: windows (LOS-only) sized to the shortened wall spans.

        Floors: aligned to the wall extents and kept triangular:
        - Ground: full 12x6 footprint
        - 1st: right triangle with legs 8 (x) and 3 (y), right angle at the connecting corner (0,6)
        - 2nd: right triangle with legs 6 (x) and 2 (y), right angle at the connecting corner (0,6)
        """
        footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # Centerlines inset by 0.25" so buffered walls remain within footprint
        y_top_cl = 6.0 - half_t  # 5.75
        x_left_cl = 0.0 + half_t  # 0.25

        # Top wall spans (buffered to reach x=0..N)
        top_line_g = LineString([(0.0 + half_t, y_top_cl), (8.0 - half_t, y_top_cl)])
        top_line_l1 = LineString([(0.0 + half_t, y_top_cl), (8.0 - half_t, y_top_cl)])
        top_line_l2 = LineString([(0.0 + half_t, y_top_cl), (6.0 - half_t, y_top_cl)])

        # Left wall spans (buffered to reach y=Y0..6)
        left_line_g = LineString([(x_left_cl, 2.0 + half_t), (x_left_cl, 6.0 - half_t)])
        left_line_l1 = LineString([(x_left_cl, 3.0 + half_t), (x_left_cl, 6.0 - half_t)])
        left_line_l2 = LineString([(x_left_cl, 4.0 + half_t), (x_left_cl, 6.0 - half_t)])

        # Walls: 4" tall at each level (standard RUINS_FLOOR_HEIGHT)
        add_wall(top_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(left_line_g.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

        add_wall(top_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
        add_wall(left_line_l1.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)

        # 2nd floor is a low parapet (1") rather than a full-height wall; no windows there.
        add_wall(top_line_l2.buffer(half_t), floor_level=2, height=1.0)
        add_wall(left_line_l2.buffer(half_t), floor_level=2, height=1.0)

        # Windows (LOS only): keep within a ~3" wall height (0.75"-2.25" above that floor)
        z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
        z1_top = 2.25 + RUINS_FLOOR_HEIGHT

        # 1st floor windows
        # Top wall span x=0..8: two 2" windows
        for x_start, x_end in [(1.0, 3.0), (4.0, 6.0)]:
            openings.append({
                "polygon": box(x_start, y_top_cl - half_t, x_end, y_top_cl + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True,
            })
        # Left wall span y=3..6 (3" total): one vertical window centered in span
        openings.append({
            "polygon": box(x_left_cl - half_t, 3.5, x_left_cl + half_t, 5.5),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        })

        # Floors (aligned to the wall extents; triangular)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        # First floor: right triangle legs 8 (x) and 3 (y), right angle at (0,6)
        floor1 = Polygon([(0.0, 6.0), (8.0, 6.0), (0.0, 3.0)])
        floors.append({
            "polygon": floor1,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        # Second floor: right triangle legs 6 (x) and 2 (y), right angle at (0,6)
        floor2 = Polygon([(0.0, 6.0), (6.0, 6.0), (0.0, 4.0)])
        floors.append({
            "polygon": floor2,
            "elevation": RUINS_FLOOR_HEIGHT * 2.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_6x4_variant1() -> RuinsTerrain:
        """Create a low RUINS preset (6" x 4") Variant 1 - rubble/debris/broken columns.

        This is intended for the blue-dotted rectangles in the GT layout diagrams:
        - Max height: 2" (so it behaves like low rubble rather than tall LOS-blocking ruins)
        - No upper floors
        - A handful of small, irregular-ish obstacles inside the footprint to represent
          broken columns / rocks. These are modeled as RUINS walls (solid, no movement through)
          at z ∈ [0, 2].
        """
        # Footprint polygon (authored at origin)
        footprint = Polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_rubble(poly: Polygon) -> None:
            # Keep it simple: treat rubble as short solid obstacles
            walls.append({
                "polygon": poly,
                "z_bottom": 0.0,
                "z_top": 2.0,
                "thickness": wall_thickness,
            })

        # A deterministic scatter of rubble/columns (all kept within the footprint)
        # Sizes are small enough to "look like" debris without forming a full wall.
        rubble_pieces = [
            box(0.6, 0.6, 1.3, 1.4),   # broken column base
            box(2.0, 0.8, 2.6, 1.6),   # rocks
            box(4.4, 0.7, 5.2, 1.3),   # column
            box(1.0, 2.4, 1.8, 3.2),   # rubble pile
            box(2.8, 2.2, 3.6, 3.0),   # rocks
            box(4.2, 2.5, 5.4, 3.1),   # broken wall chunk
        ]
        for rp in rubble_pieces:
            add_rubble(rp)

        # Ground surface (primarily for floor-level determination); low rubble has no upper floors.
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_6x4_variant2() -> RuinsTerrain:
        """Create RUINS preset (6" x 4") Variant 2 - corner ruin (left + bottom walls), no openings.

        - Footprint: 6x4 rectangle
        - Ground walls: full-height (4") along:
          • Left short edge (x=0, y=0..4)
          • Bottom long edge (y=0, x=0..6)
        - Floors: ground + one upper floor (full footprint)
        - Upper level: 1" parapet along the same two edges (left + bottom)
        - No doors, no windows
        """
        footprint = Polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # Centerlines inset so buffered walls remain within footprint
        x_left_cl = 0.0 + half_t
        y_bottom_cl = 0.0 + half_t

        left_line = LineString([(x_left_cl, 0.0 + half_t), (x_left_cl, 4.0 - half_t)])
        bottom_line = LineString([(0.0 + half_t, y_bottom_cl), (6.0 - half_t, y_bottom_cl)])

        # Ground full-height walls
        add_wall(left_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(bottom_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

        # Floors: ground + one upper floor (full footprint)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        floors.append({
            "polygon": footprint,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        # Upper parapet (1") along same edges
        parapet_h = 1.0
        add_wall(left_line.buffer(half_t), floor_level=1, height=parapet_h)
        add_wall(bottom_line.buffer(half_t), floor_level=1, height=parapet_h)

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant4() -> RuinsTerrain:
        """Create RUINS preset (12" x 6") Variant 4 - 8x6 two-level section + 4x6 low rubble.

        Structure (authored at origin):
        - Overall footprint: 12x6 rectangle
        - Left section (x=0..4, y=0..6): low rubble (<=2" height)
        - Right section (x=4..12, y=0..6): a solid 8x6 structure with:
          • Ground floor (level 0): present
          • First floor (level 1): platform 8x4 on the TOP edge (y=2..6)
          • No doors, no windows (openings list is empty)
          • Walls only exist on the TOP long edge of the 8" section (y=6, x=4..12)
          • First floor has a short parapet wall (~2" height) on that same top edge
        """
        footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []  # explicitly none
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # --- Low rubble section (x=0..4, y=0..6), max height 2"
        def add_rubble(poly: Polygon) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": 0.0,
                "z_top": 2.0,
                "thickness": wall_thickness,
            })

        rubble_pieces = [
            box(0.5, 0.6, 1.4, 1.5),
            box(2.0, 0.8, 3.5, 1.6),
            box(0.7, 2.2, 1.6, 3.1),
            box(2.3, 2.6, 3.7, 3.3),
            box(0.6, 4.2, 1.8, 5.0),
            box(2.2, 4.4, 3.6, 5.3),
        ]
        for rp in rubble_pieces:
            add_rubble(rp)

        # --- 8x6 two-level section (x=4..12, y=0..6)
        # Walls: ONLY the top long edge wall (y=6) for the 8" span (x=4..12).
        # Plus a 4" wall segment on the right edge (x=12) spanning y=2..6.
        # Use inset centerline so buffered wall stays within the footprint.
        y2 = 2.0
        top_line = LineString([(4.0 + half_t, 6.0 - half_t), (12.0 - half_t, 6.0 - half_t)])
        right_line_4in = LineString([(12.0 - half_t, y2 + half_t), (12.0 - half_t, 6.0 - half_t)])
        add_wall(top_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(right_line_4in.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

        # First-floor platform: 8x4 on the TOP edge (y=2..6)
        floor1_poly = box(4.0, 2.0, 12.0, 6.0)

        # Short parapet on first floor (1" tall) on the top and right edges.
        parapet_h = 1.0
        p_top = LineString([(4.0 + half_t, 6.0 - half_t), (12.0 - half_t, 6.0 - half_t)]).buffer(half_t)
        p_right_4in = LineString([(12.0 - half_t, y2 + half_t), (12.0 - half_t, 6.0 - half_t)]).buffer(half_t)
        add_wall(p_top, floor_level=1, height=parapet_h)
        add_wall(p_right_4in, floor_level=1, height=parapet_h)

        # Floors: ground floor (full footprint); first floor (platform only)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        floors.append({
            "polygon": floor1_poly,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant5() -> RuinsTerrain:
        """Create RUINS preset (12" x 6") Variant 5 - Variant4 with the corner walls anchored bottom-right.

        Variant 5 is a vertical mirror of Variant 4 across the horizontal axis through y=3,
        so the 4" right-edge wall segment (and its floor-1 parapet) that is anchored to the
        top-right corner in Variant 4 becomes anchored to the bottom-right corner.
        """
        v4 = TerrainFactory.create_preset_ruin_rect_12x6_variant4()
        try:
            from shapely.affinity import scale as _sh_scale
        except Exception:
            return v4

        def _mirror_geom(g):
            try:
                # Mirror top/bottom within 0..6 by flipping y about y=3
                return _sh_scale(g, xfact=1.0, yfact=-1.0, origin=(0.0, 3.0))
            except Exception:
                return g

        footprint = _mirror_geom(v4.footprint)
        walls: List[dict] = []
        for w in v4.walls:
            walls.append({
                "polygon": _mirror_geom(w["polygon"]),
                "z_bottom": w["z_bottom"],
                "z_top": w["z_top"],
                "thickness": w.get("thickness", 0.5),
            })
        openings: List[dict] = []
        for op in v4.openings:
            openings.append({
                "polygon": _mirror_geom(op["polygon"]),
                "z_bottom": op["z_bottom"],
                "z_top": op["z_top"],
                "allows_movement": op.get("allows_movement", False),
                "allows_los": op.get("allows_los", False),
            })
        floors: List[dict] = []
        for fl in v4.floors:
            floors.append({
                "polygon": _mirror_geom(fl["polygon"]),
                "elevation": fl["elevation"],
                "thickness": fl.get("thickness", 0.5),
            })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant6() -> RuinsTerrain:
        """Create RUINS preset (12" x 6") Variant 6 - rubble / ruin / rubble (2 + 8 + 2).

        Structure (authored at origin):
        - Overall footprint: 12x6
        - Section 1 (x=0..2): 2x6 low rubble (<=2")
        - Section 2 (x=2..10): 8x6 ruins with:
          • Walls (no doors):
            - Short-edge wall on the LEFT side of the ruins section: 5" tall span (y=0..5) at x=2
            - Long-edge wall on the BOTTOM of the ruins section: 7" span (x=2..9) at y=0
          • Floors: ground, floor 1, floor 2 (platforms on the 8x6 section only for floors 1/2)
          • Floor 1: windows (LOS-only): 2 on the long-edge wall, 1 on the short-edge wall
          • Floor 2: parapets (1") along the same two wall edges, no windows
        - Section 3 (x=10..12): 2x6 low rubble (<=2")
        """
        footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # --- Rubble sections (x=0..2 and x=10..12), <=2"
        def add_rubble(poly: Polygon) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": 0.0,
                "z_top": 2.0,
                "thickness": wall_thickness,
            })

        rubble_left = [
            box(0.2, 0.6, 0.8, 1.4),
            box(1.0, 0.8, 1.8, 1.5),
            box(0.3, 2.4, 1.2, 3.2),
            box(1.1, 3.0, 1.9, 3.8),
            box(0.2, 4.6, 1.0, 5.4),
            box(1.1, 4.4, 1.9, 5.3),
        ]
        rubble_right = [
            box(10.2, 0.6, 10.9, 1.3),
            box(11.1, 0.8, 11.8, 1.5),
            box(10.3, 2.3, 11.0, 3.1),
            box(11.1, 2.7, 11.8, 3.5),
            box(10.2, 4.5, 11.0, 5.3),
            box(11.1, 4.4, 11.8, 5.2),
        ]
        for rp in rubble_left:
            add_rubble(rp)
        for rp in rubble_right:
            add_rubble(rp)

        # --- Ruins section (x=2..10, y=0..6)
        x_left = 2.0
        x_right = 10.0
        y_bottom = 0.0

        # Walls are authored so buffered polygons remain inside the overall footprint.
        # Left wall is along the join at x=2 (buffered into both sections), length 5" from y=0..5.
        left_line = LineString([(x_left, y_bottom + half_t), (x_left, 5.0 - half_t)])
        # Bottom wall along y=0, 7" from x=2..9.
        bottom_line = LineString([(x_left + half_t, y_bottom + half_t), (9.0 - half_t, y_bottom + half_t)])

        # Ground + first floor full-height walls
        add_wall(left_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(bottom_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(left_line.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)
        add_wall(bottom_line.buffer(half_t), floor_level=1, height=RUINS_FLOOR_HEIGHT)

        # Floor 2 parapets (1") on the same edges
        parapet_h = 1.0
        add_wall(left_line.buffer(half_t), floor_level=2, height=parapet_h)
        add_wall(bottom_line.buffer(half_t), floor_level=2, height=parapet_h)

        # Windows (LOS only) on floor 1
        z1_bottom = 0.75 + RUINS_FLOOR_HEIGHT
        z1_top = 2.25 + RUINS_FLOOR_HEIGHT

        # Bottom wall windows: two 2" windows within x=2..9
        for x0, x1 in [(3.0, 5.0), (6.0, 8.0)]:
            openings.append({
                "polygon": box(x0, y_bottom + half_t - half_t, x1, y_bottom + half_t + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True,
            })

        # Left wall window: one 2" vertical window within y=0..5
        openings.append({
            "polygon": box(x_left - half_t, 1.5, x_left + half_t, 3.5),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True,
        })

        # Floors
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        # Upper floors are triangular platforms anchored at the wall corner (x=2,y=0),
        # matching the two wall spans: bottom leg 7" (x=2..9) and left leg 5" (y=0..5).
        ruins_floor_tri = Polygon([(x_left, 0.0), (9.0, 0.0), (x_left, 5.0)])
        floors.append({
            "polygon": ruins_floor_tri,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        floors.append({
            "polygon": ruins_floor_tri,
            "elevation": RUINS_FLOOR_HEIGHT * 2.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_10x5_variant1() -> RuinsTerrain:
        """Create RUINS preset (10" x 5") Variant 1 - 3.5x5 rubble + 6.5x5 two-level ruins.

        Structure (authored at origin):
        - Overall footprint: 10x5 rectangle
        - Left section (x=0..3.5, y=0..5): low rubble (<=2" height)
        - Right section (x=3.5..10, y=0..5): a 6.5x5 two-level ruins section with:
          • Ground + first floor platform (full 6.5x5)
          • No doors, no windows
          • Walls only on:
            - The joining edge between the two sections (x=3.5, y=0..5)
            - The top edge of the 6.5" section (y=5, x=3.5..10)
          • First-floor parapet (1" tall) along those same edges
        """
        footprint = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []  # explicitly none
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # --- Low rubble section (x=0..3.5, y=0..5), max height 2"
        def add_rubble(poly: Polygon) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": 0.0,
                "z_top": 2.0,
                "thickness": wall_thickness,
            })

        rubble_pieces = [
            box(0.4, 0.5, 1.1, 1.2),
            box(1.6, 0.6, 2.6, 1.3),
            box(0.6, 2.0, 1.4, 2.8),
            box(2.0, 2.2, 3.1, 3.0),
            box(0.5, 3.7, 1.5, 4.4),
            box(2.1, 3.6, 3.3, 4.3),
        ]
        for rp in rubble_pieces:
            add_rubble(rp)

        # --- 6.5x5 two-level ruins section (x=3.5..10, y=0..5)
        x_join = 3.5
        y_top = 5.0

        # Join wall is internal, can sit on x=3.5; keep endpoints inset in y.
        join_line = LineString([(x_join, 0.0 + half_t), (x_join, y_top - half_t)])
        # Top wall needs to be inset in y to keep buffered wall inside footprint.
        top_line = LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)])

        add_wall(join_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(top_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

        # First-floor platform is the full 6.5x5 section
        floor1_poly = box(x_join, 0.0, 10.0, y_top)

        # First-floor parapet (1") along same edges as walls
        parapet_h = 1.0
        p_join = LineString([(x_join, 0.0 + half_t), (x_join, y_top - half_t)]).buffer(half_t)
        p_top = LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t)
        add_wall(p_join, floor_level=1, height=parapet_h)
        add_wall(p_top, floor_level=1, height=parapet_h)

        # Floors: ground (full footprint), first (ruins section)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        floors.append({
            "polygon": floor1_poly,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_10x5_variant2() -> RuinsTerrain:
        """Create RUINS preset (10" x 5") Variant 2 - like Variant 1, but move the join wall to x=10.

        Same footprint/sections as Variant 1:
        - Overall footprint: 10x5 rectangle
        - Left section (x=0..3.5): low rubble (<=2")
        - Right section (x=3.5..10): 6.5x5 two-level ruins (ground + floor 1)

        Walls (no windows/doors):
        - Top wall on the 6.5" section (y=5, x=3.5..10)
        - Right wall on the 5" edge (x=10, y=0..5)  <-- join wall moved from x=3.5 to x=10

        First-floor parapet (1") runs along the same two edges as the walls.
        """
        footprint = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []  # explicitly none
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # --- Low rubble section (x=0..3.5, y=0..5), max height 2"
        def add_rubble(poly: Polygon) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": 0.0,
                "z_top": 2.0,
                "thickness": wall_thickness,
            })

        rubble_pieces = [
            box(0.4, 0.5, 1.1, 1.2),
            box(1.6, 0.6, 2.6, 1.3),
            box(0.6, 2.0, 1.4, 2.8),
            box(2.0, 2.2, 3.1, 3.0),
            box(0.5, 3.7, 1.5, 4.4),
            box(2.1, 3.6, 3.3, 4.3),
        ]
        for rp in rubble_pieces:
            add_rubble(rp)

        # --- 6.5x5 two-level ruins section (x=3.5..10, y=0..5)
        x_join = 3.5
        y_top = 5.0

        # Right wall at x=10 (moved from x=3.5), inset in y
        right_line = LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)])
        # Top wall on the 6.5" section (y=5), inset in y
        top_line = LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)])

        add_wall(right_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(top_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

        # First-floor platform is the full 6.5x5 section
        floor1_poly = box(x_join, 0.0, 10.0, y_top)

        # First-floor parapet (1") along same edges as walls
        parapet_h = 1.0
        p_right = LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t)
        p_top = LineString([(x_join + half_t, y_top - half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t)
        add_wall(p_right, floor_level=1, height=parapet_h)
        add_wall(p_top, floor_level=1, height=parapet_h)

        # Floors: ground (full footprint), first (ruins section)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        floors.append({
            "polygon": floor1_poly,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)

    @staticmethod
    def create_preset_ruin_rect_10x5_variant3() -> RuinsTerrain:
        """Create RUINS preset (10" x 5") Variant 3 - like Variant 2, but move the long-edge wall to y=0.

        Same footprint/sections as Variant 1:
        - Overall footprint: 10x5 rectangle
        - Left section (x=0..3.5): low rubble (<=2")
        - Right section (x=3.5..10): 6.5x5 two-level ruins (ground + floor 1)

        Walls (no windows/doors):
        - Right wall on the 5" edge (x=10, y=0..5)
        - Bottom wall on the 6.5" section (y=0, x=3.5..10)  <-- moved from y=5 in Variant 2

        First-floor parapet (1") runs along the same two edges as the walls.
        """
        footprint = Polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)])

        wall_thickness = RUINS_WALL_THICKNESS
        half_t = wall_thickness / 2.0

        walls: List[dict] = []
        openings: List[dict] = []  # explicitly none
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * RUINS_FLOOR_HEIGHT),
                "z_top": float(floor_level * RUINS_FLOOR_HEIGHT + height),
                "thickness": wall_thickness,
            })

        # --- Low rubble section (x=0..3.5, y=0..5), max height 2"
        def add_rubble(poly: Polygon) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": 0.0,
                "z_top": 2.0,
                "thickness": wall_thickness,
            })

        rubble_pieces = [
            box(0.4, 0.5, 1.1, 1.2),
            box(1.6, 0.6, 2.6, 1.3),
            box(0.6, 2.0, 1.4, 2.8),
            box(2.0, 2.2, 3.1, 3.0),
            box(0.5, 3.7, 1.5, 4.4),
            box(2.1, 3.6, 3.3, 4.3),
        ]
        for rp in rubble_pieces:
            add_rubble(rp)

        # --- 6.5x5 two-level ruins section (x=3.5..10, y=0..5)
        x_join = 3.5
        y_top = 5.0

        # Right wall at x=10 (inset in y)
        right_line = LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)])
        # Bottom wall on the 6.5" section (y=0), inset in y
        bottom_line = LineString([(x_join + half_t, 0.0 + half_t), (10.0 - half_t, 0.0 + half_t)])

        add_wall(right_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)
        add_wall(bottom_line.buffer(half_t), floor_level=0, height=RUINS_FLOOR_HEIGHT)

        # First-floor platform is the full 6.5x5 section
        floor1_poly = box(x_join, 0.0, 10.0, y_top)

        # First-floor parapet (1") along same edges as walls
        parapet_h = 1.0
        p_right = LineString([(10.0 - half_t, 0.0 + half_t), (10.0 - half_t, y_top - half_t)]).buffer(half_t)
        p_bottom = LineString([(x_join + half_t, 0.0 + half_t), (10.0 - half_t, 0.0 + half_t)]).buffer(half_t)
        add_wall(p_right, floor_level=1, height=parapet_h)
        add_wall(p_bottom, floor_level=1, height=parapet_h)

        # Floors: ground (full footprint), first (ruins section)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": RUINS_FLOOR_THICKNESS,
        })
        floors.append({
            "polygon": floor1_poly,
            "elevation": RUINS_FLOOR_HEIGHT,
            "thickness": RUINS_FLOOR_THICKNESS,
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)


def validate_ruins_placement(unit: 'Unit', position: Tuple[float, float, float], 
                            terrain_features: List['TerrainFeature'], moving_model: Optional['Model'] = None) -> dict:
    """
    Validate if a unit or a specific moving model can be placed at a position considering RUINS terrain rules.

    - If moving_model is provided, only that model's base at `position` is validated for overhang on upper floors
      (used during per-model movement/pathfinding).
    - If moving_model is None, validates the entire unit (used during deployment where positions are pre-set).
    
    Args:
        unit: Unit to validate placement for
        position: (x, y, z) position to check
        terrain_features: List of terrain features to check against
        moving_model: Optional specific model being placed/moved
    
    Returns:
        Dict with 'valid' (bool), 'reason' (str), and 'floor_level' (int) keys
    """
    x, y, z = position
    
    # Check each terrain feature for RUINS
    for terrain in terrain_features:
        if terrain.terrain_type != TerrainType.RUINS:
            continue
            
        # Check if the MODEL BASE intersects this RUINS footprint (not just the centroid)
        if moving_model is not None:
            try:
                test_base = moving_model.model_base.get_base_shape_at(x, y, getattr(moving_model.model_base, 'facing', 0.0))
            except Exception:
                test_base = None
            if test_base is None or not test_base.intersects(terrain.footprint):
                continue
        else:
            # Validate entire unit: only proceed if any model's base intersects the footprint
            any_intersection = False
            for m in unit.models:
                mpos = m.get_location()
                if not mpos:
                    continue
                mx, my = mpos[0], mpos[1]
                try:
                    m_base = m.model_base.get_base_shape_at(mx, my, getattr(m.model_base, 'facing', 0.0))
                except Exception:
                    m_base = None
                if m_base is not None and m_base.intersects(terrain.footprint):
                    any_intersection = True
                    break
            if not any_intersection:
                continue
            
        # Find which floor this z-coordinate corresponds to
        floors = getattr(terrain, 'floors', []) or []
        current_floor = None
        floor_level = 0
        
        # Find the closest floor by elevation
        closest_floor_distance = float('inf')
        for floor in floors:
            floor_elev = floor.get('elevation', 0.0)
            floor_thickness = floor.get('thickness', RUINS_FLOOR_THICKNESS)
            floor_surface = floor_elev + floor_thickness
            
            # Check if z is close to this floor surface
            distance = abs(z - floor_surface)
            if distance < closest_floor_distance and distance < 1.0:  # Allow 1" tolerance
                closest_floor_distance = distance
                current_floor = floor
                floor_level = int(round(float(floor_elev) / float(RUINS_FLOOR_HEIGHT)))
        
        # If no floor found, assume ground level (z=0) is valid
        if current_floor is None:
            if abs(z) < 1.0:  # Close to ground level
                floor_level = 0
                # Create a virtual ground floor for validation
                current_floor = {'polygon': terrain.footprint, 'elevation': 0.0, 'thickness': 0.0}
            else:
                return {'valid': False, 'reason': f'Position not on a valid floor level (z={z:.1f})', 'floor_level': 0}

        # Helper to check base-vs-wall intersection for one model at (mx,my,mz)
        def _base_overlaps_wall(model: 'Model', mx: float, my: float, mz: float) -> Optional[str]:
            base_geom = None
            try:
                base_geom = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, 'facing', 0.0))
            except Exception:
                return 'Failed to get model base geometry for wall check'
            for wall in getattr(terrain, 'walls', []) or []:
                # Only consider walls that occupy this Z slice
                if wall.get('z_bottom', 0.0) <= mz <= wall.get('z_top', 0.0):
                    try:
                        if base_geom.intersects(wall.get('polygon')):
                            return 'Model base overlaps a RUINS wall'
                    except Exception:
                        # If intersection fails, be conservative and reject
                        return 'Error during wall intersection check'
            return None
        
        # Ground floor (level 0) - allowed anywhere the base does not overlap walls,
        # with vertical clearance check if an upper floor exists directly overhead at this XY.
        if floor_level == 0:
            if moving_model is not None:
                wall_reason = _base_overlaps_wall(moving_model, x, y, z)
                if wall_reason:
                    return {'valid': False, 'reason': wall_reason, 'floor_level': floor_level}
                # Vertical clearance: if base is under any upper-floor polygon, ensure model height fits the gap
                try:
                    base_geom_gf = moving_model.model_base.get_base_shape_at(x, y, getattr(moving_model.model_base, 'facing', 0.0))
                except Exception:
                    base_geom_gf = None
                if base_geom_gf is not None:
                    # Find the nearest upper floor above this ground floor whose polygon overlaps the base
                    nearest_upper_floor = None
                    min_elev = float('inf')
                    for fl in floors:
                        elev = fl.get('elevation', 0.0)
                        if elev <= 0.0:
                            continue  # Only consider floors above ground
                        fl_poly = fl.get('polygon')
                        if fl_poly is None:
                            continue
                        try:
                            overlaps_xy = base_geom_gf.intersects(fl_poly)
                        except Exception:
                            overlaps_xy = False
                        if not overlaps_xy:
                            continue
                        if elev < min_elev:
                            min_elev = elev
                            nearest_upper_floor = fl
                    if nearest_upper_floor is not None:
                        # Compute gap from top of current floor to bottom of next floor
                        current_top = (current_floor.get('elevation', 0.0) + current_floor.get('thickness', RUINS_FLOOR_THICKNESS))
                        next_bottom = nearest_upper_floor.get('elevation', 0.0)
                        vertical_gap = max(0.0, next_bottom - current_top)
                        # Require model height to be strictly less than the gap minus a small safety buffer
                        safety_buffer = 0.10
                        model_height = getattr(moving_model.model_base, 'model_height', 2.0)
                        if model_height >= max(0.0, vertical_gap - safety_buffer):
                            return {
                                'valid': False,
                                'reason': f'Model height {model_height:.2f}" exceeds available vertical gap {vertical_gap:.2f}" under next floor',
                                'floor_level': floor_level
                            }
            else:
                # Validate all models in the unit at their current positions (deployment-time).
                # Use collision models so attached leaders are validated as part of the unit.
                try:
                    models = unit.get_models_for_collision()
                except Exception:
                    models = unit.models
                for model in models:
                    model_pos = model.get_location()
                    if not model_pos:
                        continue
                    mx, my, mz = model_pos[0], model_pos[1], model_pos[2] if len(model_pos) > 2 else 0.0
                    wall_reason = _base_overlaps_wall(model, mx, my, mz)
                    if wall_reason:
                        return {'valid': False, 'reason': wall_reason, 'floor_level': floor_level}
                    # Vertical clearance: if base is under any upper-floor polygon, ensure model height fits the gap
                    try:
                        base_geom_gf = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, 'facing', 0.0))
                    except Exception:
                        base_geom_gf = None
                    if base_geom_gf is not None:
                        nearest_upper_floor = None
                        min_elev = float('inf')
                        for fl in floors:
                            elev = fl.get('elevation', 0.0)
                            if elev <= 0.0:
                                continue
                            fl_poly = fl.get('polygon')
                            if fl_poly is None:
                                continue
                            try:
                                overlaps_xy = base_geom_gf.intersects(fl_poly)
                            except Exception:
                                overlaps_xy = False
                            if not overlaps_xy:
                                continue
                            if elev < min_elev:
                                min_elev = elev
                                nearest_upper_floor = fl
                        if nearest_upper_floor is not None:
                            current_top = (current_floor.get('elevation', 0.0) + current_floor.get('thickness', RUINS_FLOOR_THICKNESS))
                            next_bottom = nearest_upper_floor.get('elevation', 0.0)
                            vertical_gap = max(0.0, next_bottom - current_top)
                            safety_buffer = 0.10
                            model_height = getattr(model.model_base, 'model_height', 2.0)
                            if model_height >= max(0.0, vertical_gap - safety_buffer):
                                return {
                                    'valid': False,
                                    'reason': f'Model height {model_height:.2f}" exceeds available vertical gap {vertical_gap:.2f}" under next floor',
                                    'floor_level': floor_level
                                }
            return {'valid': True, 'reason': 'Valid ground floor placement', 'floor_level': floor_level}
        
        # Upper floors - check unit restrictions
        if not unit.can_access_upper_floors():
            return {
                'valid': False, 
                'reason': f'Unit type cannot access upper floors (floor level {floor_level})',
                'floor_level': floor_level
            }
        
        # Check base overhang for upper floors (no overhang allowed on any upper floor)
        floor_poly = current_floor.get('polygon')
        if floor_level > 0 and floor_poly:
            # If a specific moving model is provided, only validate this model at the proposed position
            if moving_model is not None:
                base_geom = moving_model.model_base.get_base_shape_at(x, y, getattr(moving_model.model_base, 'facing', 0.0))
                # "Wholly within" should allow touching the boundary
                ok = False
                try:
                    if hasattr(floor_poly, "covers"):
                        ok = floor_poly.covers(base_geom)
                    else:
                        ok = floor_poly.contains(base_geom)
                except Exception:
                    ok = False
                if not ok:
                    return {
                        'valid': False,
                        'reason': f'Model base would overhang floor on level {floor_level}',
                        'floor_level': floor_level
                    }
            else:
                # Deployment-time check for all models (positions assumed to be already set on models)
                try:
                    models = unit.get_models_for_collision()
                except Exception:
                    models = unit.models
                for model in models:
                    model_pos = model.get_location()
                    if model_pos:
                        mx, my = model_pos[0], model_pos[1]
                        base_geom = model.model_base.get_base_shape_at(mx, my, getattr(model.model_base, 'facing', 0.0))
                        ok = False
                        try:
                            if hasattr(floor_poly, "covers"):
                                ok = floor_poly.covers(base_geom)
                            else:
                                ok = floor_poly.contains(base_geom)
                        except Exception:
                            ok = False
                        if not ok:
                            return {
                                'valid': False,
                                'reason': f'Model base would overhang floor on level {floor_level}',
                                'floor_level': floor_level
                            }

        # On all upper floors, also forbid base overlap with walls at the model's Z
        if floor_level > 0:
            if moving_model is not None:
                wall_reason = _base_overlaps_wall(moving_model, x, y, z)
                if wall_reason:
                    return {'valid': False, 'reason': wall_reason, 'floor_level': floor_level}
            else:
                try:
                    models = unit.get_models_for_collision()
                except Exception:
                    models = unit.models
                for model in models:
                    model_pos = model.get_location()
                    if not model_pos:
                        continue
                    mx, my, mz = model_pos[0], model_pos[1], model_pos[2] if len(model_pos) > 2 else (x, y, z)[2]
                    wall_reason = _base_overlaps_wall(model, mx, my, mz)
                    if wall_reason:
                        return {'valid': False, 'reason': wall_reason, 'floor_level': floor_level}
        
        return {'valid': True, 'reason': f'Valid upper floor placement (level {floor_level})', 'floor_level': floor_level}
    
    # No RUINS terrain at this position
    return {'valid': True, 'reason': 'No RUINS terrain at position', 'floor_level': 0}


class ObjectivePoint:
    def __init__(self, x: float, y: float, z: float = 0.0, control_radius: float = 3.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.control_radius = control_radius
        self.controlling_player = None
        # Chapter Approved 2025/26 Terraform tracking
        self.terraformed_by = None
        # Chapter Approved 2025/26 Cleanse tracking
        self.cleansed_by = None
        # Chapter Approved 2025/26 Unexploded Ordnance tracking (Hazard markers)
        self.is_hazard: bool = False
        # Some primaries can remove objectives (e.g., Scorched Earth, Supply Drop)
        self.removed = False

    def update_control(self, game_state: 'Game') -> None:
        # Determine which player controls the objective based on base overlap
        player_oc = {player: 0 for player in game_state.players}  # Initialize all players with 0 OC
        
        from shapely.geometry import Point
        # If removed, always uncontrolled
        if getattr(self, 'removed', False):
            self.controlling_player = None
            return
        # Create objective area as a circle
        objective_area = Point(self.x, self.y).buffer(self.control_radius)
        
        for player in game_state.players:
            if not player.army:
                continue
            for unit in player.army.units:
                # Avoid double-counting: attached leaders are counted as part of their bodyguard unit.
                try:
                    if bool(getattr(unit, "is_leader", False)) and getattr(unit, "attached_to", None) is not None:
                        continue
                except Exception:
                    pass
                if not unit.deployed or not unit.is_alive():
                    continue
                try:
                    models = unit.get_models_for_collision()
                except Exception:
                    models = unit.models
                for model in models:
                    if not model.is_alive:
                        continue
                    
                    # Get model's base shape and check for overlap with objective area
                    try:
                        model_base_shape = model.model_base.get_base_shape()
                        if model_base_shape.intersects(objective_area):
                            player_oc[player] += model.objective_control
                            print(f"🎯 {model.name} (OC: {model.objective_control}) overlaps objective at ({self.x:.1f}, {self.y:.1f})")
                    except Exception as e:
                        # Fallback to distance check if base shape fails
                        distance = get_dist(self.x - model.model_base.x, self.y - model.model_base.y)
                        model_base_radius = getattr(model.model_base, 'get_radius', lambda: 1.0)()
                        if distance <= (self.control_radius + model_base_radius):
                            player_oc[player] += model.objective_control
                            print(f"🎯 {model.name} (OC: {model.objective_control}) near objective (fallback calculation)")

        # Determine controlling player based on OC values
        if any(oc > 0 for oc in player_oc.values()):
            max_oc = max(player_oc.values())
            max_players = [player for player, oc in player_oc.items() if oc == max_oc]
            if len(max_players) == 1:
                self.controlling_player = max_players[0]
            else:
                # Tie - no one controls the objective
                self.controlling_player = None
        else:
            self.controlling_player = None
        
        # Debug output
        oc_summary = {player.name: oc for player, oc in player_oc.items() if oc > 0}
        if oc_summary:
            print(f"ObjectivePoint ({self.x:.1f}, {self.y:.1f}) OC values: {oc_summary} -> controlled by {self.controlling_player.name if self.controlling_player else 'None'}")
        else:
            print(f"ObjectivePoint ({self.x:.1f}, {self.y:.1f}) controlled by None (no models in range)")


class ObjectiveCategory(Enum):
    PRIMARY = auto()
    SECONDARY = auto()
    SECRET = auto()


class Objective:
    def __init__(self, name: str, category: ObjectiveCategory, points: int, description: str, conditions: callable, location: Optional[Tuple[float, float]] = None) -> None:
        """
        Represents an objective in Warhammer 40,000.
        
        Parameters:
        - name (str): Name of the objective.
        - category (ObjectiveCategory): Primary, Secondary, or Secret.
        - points (int): Points rewarded upon completion.
        - description (str): Explanation of the objective's goal.
        - conditions (callable): A function or lambda to check if the objective is achieved.
        - location (tuple): (x, y) coordinates for objectives on the map (optional).
        """
        self.name = name
        self.category = category
        self.points = points
        self.description = description
        self.conditions = conditions
        self.location = location
        self.completed = False

    def check_completion(self, game_state: 'Game') -> bool:
        """Evaluate if the objective is completed based on game state."""
        self.completed = self.conditions(game_state)
        return self.completed

    def __repr__(self):
        status = "Completed" if self.completed else "Incomplete"
        return f"{self.name} ({self.category.name}): {status} - {self.points} points"
