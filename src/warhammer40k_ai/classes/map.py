from typing import List, Optional, Tuple
from enum import Enum, auto
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, convert_mm_to_inches, can_traverse_freely
from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
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
        for model in unit.models:
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
        # Check if any model in source unit is within engagement range of any model in target unit
        for source_model in source_unit.models:
            if not source_model.is_alive:
                continue
            for target_model in target_unit.models:
                if not target_model.is_alive:
                    continue
                # Calculate horizontal distance (base-to-base)
                horizontal_distance = source_model.model_base.edge_to_edge_distance(target_model.model_base)

                # Calculate vertical distance
                vertical_distance = source_model.model_base.vertical_distance(target_model.model_base)

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
                # Get height based on terrain type
                if hasattr(terrain_feature, 'height'):
                    max_height = max(max_height, terrain_feature.height)
                elif hasattr(terrain_feature, 'rim_height'):
                    max_height = max(max_height, terrain_feature.rim_height)
                else:
                    max_height = max(max_height, 2.0)  # Default terrain height

        return max_height

    def get_distance_between_units(self, unit1: Unit, unit2: Unit) -> float:
        """Calculate the shortest distance between two units.
        
        Args:
            unit1 (Unit): First unit
            unit2 (Unit): Second unit
            
        Returns:
            float: The shortest distance between any models in the two units
        """
        shortest_distance = float('inf')
        
        # Check distance between each model pair
        for model1 in unit1.models:
            for model2 in unit2.models:
                distance = model1.edge_to_edge_distance(model2)
                shortest_distance = min(shortest_distance, distance)
                
        return shortest_distance

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
        for model in unit.models:
            if model.is_alive:
                unit_pos = model.get_location()
                break

        target_pos = None
        for model in target.models:
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
                    wall_height: float = 4.0, num_floors: int = 1,
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
                "thickness": 0.5
            })

        # Create walls around perimeter
        coords = list(footprint.exterior.coords)[:-1]  # Remove duplicate last point
        for i in range(len(coords)):
            start_point = coords[i]
            end_point = coords[(i + 1) % len(coords)]

            # Create wall segment with thickness
            wall_line = LineString([start_point, end_point])
            wall_polygon = wall_line.buffer(0.25)  # 0.5" thick walls

            for floor_level in range(num_floors + 1):
                walls.append({
                    "polygon": wall_polygon,
                    "z_bottom": floor_level * wall_height,
                    "z_top": (floor_level + 1) * wall_height,
                    "thickness": 0.5
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
        - Walls 2" inward from both short edges and one long edge (y=0), flush to that long edge
          • Short walls: 4" long from y=0 to y=4 at x=2 and x=10
          • Long wall: 8" long from x=2 to x=10 along y=0
        - Ground floor (level 0): 4" wall height, no windows
        - First floor (level 1): 4" wall height, windows
          • Long wall: three 2" windows, at x=[3-5], [5-7], [7-9]
          • Short walls: one 2" window each, spanning y=[2-4]
          • All windows 1"-3" above that floor (allows LOS only)
        - Second floor (level 2): 2" damaged walls, no windows
        - No doors
        """
        # Footprint polygon
        footprint = Polygon([(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)])

        wall_thickness = 0.5
        half_t = wall_thickness / 2.0

        # Define core wall line segments
        # Center wall lines are inset by 0.25" from footprint edges so buffered walls stay within footprint
        long_wall_line = LineString([(2.0, 0.25), (10.0, 0.25)])
        short_wall_left_line = LineString([(2.0, 0.25), (2.0, 3.75)])
        short_wall_right_line = LineString([(10.0, 0.25), (10.0, 3.75)])

        # Buffer to thickness to create polygons
        long_wall_poly = long_wall_line.buffer(half_t)
        short_wall_left_poly = short_wall_left_line.buffer(half_t)
        short_wall_right_poly = short_wall_right_line.buffer(half_t)

        walls: List[dict] = []
        openings: List[dict] = []
        floors: List[dict] = []

        def add_wall(poly: Polygon, floor_level: int, height: float) -> None:
            walls.append({
                "polygon": poly,
                "z_bottom": float(floor_level * 4.0),
                "z_top": float(floor_level * 4.0 + height),
                "thickness": wall_thickness
            })

        # Ground floor walls (no windows), height 4"
        add_wall(long_wall_poly, floor_level=0, height=4.0)
        add_wall(short_wall_left_poly, floor_level=0, height=4.0)
        add_wall(short_wall_right_poly, floor_level=0, height=4.0)

        # First floor walls (with windows), height 4"
        add_wall(long_wall_poly, floor_level=1, height=4.0)
        add_wall(short_wall_left_poly, floor_level=1, height=4.0)
        add_wall(short_wall_right_poly, floor_level=1, height=4.0)

        # Windows on first floor: 1"-3" above the floor
        z1_bottom = 1.0 + 4.0
        z1_top = 3.0 + 4.0

        # Long wall: three 2" windows at 1" from each end and centered segments
        for x_start, x_end in [(3.0, 5.0), (5.0, 7.0), (7.0, 9.0)]:
            openings.append({
                # Align with long wall thickness at y = 0.25 ± 0.25
                "polygon": box(x_start, 0.25 - half_t, x_end, 0.25 + half_t),
                "z_bottom": z1_bottom,
                "z_top": z1_top,
                "allows_movement": False,
                "allows_los": True
            })

        # Short wall windows: y from 1" to 3", centered on x=2 and x=10 lines
        openings.append({
            "polygon": box(2.0 - half_t, 1.0, 2.0 + half_t, 3.0),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True
        })
        openings.append({
            "polygon": box(10.0 - half_t, 1.0, 10.0 + half_t, 3.0),
            "z_bottom": z1_bottom,
            "z_top": z1_top,
            "allows_movement": False,
            "allows_los": True
        })

        # Second floor walls (damaged), height 2"
        add_wall(long_wall_poly, floor_level=2, height=2.0)
        add_wall(short_wall_left_poly, floor_level=2, height=2.0)
        add_wall(short_wall_right_poly, floor_level=2, height=2.0)

        # Floors: ground (0) uses full footprint; upper floors are exactly 8" x 4" inside the walls, offset from y=0.25
        upper_floor_poly = box(2.0, 0.25, 10.0, 4.0)
        floors.append({
            "polygon": footprint,
            "elevation": 0.0,
            "thickness": 0.5
        })
        floors.append({
            "polygon": upper_floor_poly,
            "elevation": 4.0,
            "thickness": 0.5
        })
        floors.append({
            "polygon": upper_floor_poly,
            "elevation": 8.0,
            "thickness": 0.5
        })

        return RuinsTerrain(footprint, walls=walls, openings=openings, floors=floors)


class ObjectivePoint:
    def __init__(self, x: float, y: float, z: float = 0.0, control_radius: float = 3.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.control_radius = control_radius
        self.controlling_player = None

    def update_control(self, game_state: 'Game') -> None:
        # Determine which player controls the objective based on base overlap
        player_oc = {player: 0 for player in game_state.players}  # Initialize all players with 0 OC
        
        from shapely.geometry import Point
        # Create objective area as a circle
        objective_area = Point(self.x, self.y).buffer(self.control_radius)
        
        for player in game_state.players:
            if not player.army:
                continue
            for unit in player.army.units:
                if not unit.deployed or not unit.is_alive():
                    continue
                for model in unit.models:
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


########################################################
### EXAMPLE OBJECTIVES
########################################################
# Primary Objective: Terraform (perform an action on objectives)
terraform_condition = lambda game_state: (
    game_state.unit_performed_action_on_objective("Terraform")
)

terraform_objective = Objective(
    name="Terraform Objective",
    category=ObjectiveCategory.PRIMARY,
    points=10,
    description="Perform a Terraform action on an objective to score points.",
    conditions=terraform_condition,
    location=(12, 8)  # Example objective location on the map
)

# Primary Objective: Take and Hold
take_and_hold_condition = lambda game_state: (
    game_state.player_controls_more_objectives()
)

take_and_hold = Objective(
    name="Take and Hold",
    category=ObjectiveCategory.PRIMARY,
    points=5,
    description="Control more objectives than your opponent at the end of the turn.",
    conditions=take_and_hold_condition
)

# Secondary Objective: Sabotage Terrain
sabotage_condition = lambda game_state: (
    game_state.unit_sabotaged_terrain("Enemy Terrain")
)

sabotage_objective = Objective(
    name="Sabotage Terrain",
    category=ObjectiveCategory.SECONDARY,
    points=5,
    description="Sabotage a terrain feature controlled by the opponent.",
    conditions=sabotage_condition
)

# Secondary Objective: Containment (units near battlefield edges)
containment_condition = lambda game_state: (
    game_state.has_units_near_edges()
)

containment_objective = Objective(
    name="Containment",
    category=ObjectiveCategory.SECONDARY,
    points=5,
    description="Maintain units within 9 inches of a battlefield edge.",
    conditions=containment_condition
)

# Secret Mission: Command Insertion (Warlord in enemy deployment)
command_insertion_condition = lambda game_state: (
    game_state.warlord_in_enemy_deployment_zone()
)

command_insertion = Objective(
    name="Command Insertion",
    category=ObjectiveCategory.SECRET,
    points=20,
    description="Move your Warlord into the enemy deployment zone.",
    conditions=command_insertion_condition
)

# Secret Mission: War of Attrition (weaken enemy forces)
war_of_attrition_condition = lambda game_state: (
    game_state.enemy_units_reduced_to_half_strength()
)

war_of_attrition = Objective(
    name="War of Attrition",
    category=ObjectiveCategory.SECRET,
    points=20,
    description="Reduce most of the enemy units to below half strength.",
    conditions=war_of_attrition_condition
)
