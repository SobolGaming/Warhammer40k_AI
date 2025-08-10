"""
Official Warhammer 40k 10th Edition Mission Deployment Zones and Objectives
Based on Chapter Approved 2025/2026 mission layouts.

Battlefield dimensions: 60" horizontal x 44" vertical
Coordinate system: (0,0) at bottom-left corner
"""

from typing import List, Dict, Tuple, Optional, Union
from enum import Enum
from dataclasses import dataclass
from .map import ObjectivePoint, Objective, ObjectiveCategory
import math


class DeploymentZoneType(Enum):
    """Types of deployment zones in official missions."""
    DEFENDER = "defender"  # Green zones
    ATTACKER = "attacker"  # Red zones
    NO_MANS_LAND = "no_mans_land"  # White/Gray zones


class CutoutType(Enum):
    """Types of cutouts that can be applied to deployment zones."""
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


@dataclass
class ZoneCutout:
    """Defines an area to be cut out from a deployment zone."""
    cutout_type: CutoutType
    center_x: float
    center_y: float
    # For CIRCLE: radius
    # For RECTANGLE: width, height  
    # For POLYGON: vertices (relative to center)
    parameters: Union[float, Tuple[float, float], List[Tuple[float, float]]]
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is within this cutout area."""
        if self.cutout_type == CutoutType.CIRCLE:
            radius = self.parameters
            distance = math.sqrt((x - self.center_x)**2 + (y - self.center_y)**2)
            return distance <= radius
        
        elif self.cutout_type == CutoutType.RECTANGLE:
            width, height = self.parameters
            half_width = width / 2
            half_height = height / 2
            return (self.center_x - half_width <= x <= self.center_x + half_width and
                    self.center_y - half_height <= y <= self.center_y + half_height)
        
        elif self.cutout_type == CutoutType.POLYGON:
            # Convert relative vertices to absolute coordinates
            vertices = [(self.center_x + dx, self.center_y + dy) for dx, dy in self.parameters]
            return self._point_in_polygon(x, y, vertices)
        
        return False
    
    def _point_in_polygon(self, x: float, y: float, vertices: List[Tuple[float, float]]) -> bool:
        """Ray casting algorithm for point-in-polygon test."""
        n = len(vertices)
        inside = False
        
        p1x, p1y = vertices[0]
        for i in range(1, n + 1):
            p2x, p2y = vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside


@dataclass
class DeploymentZone:
    """Represents a deployment zone with precise coordinates."""
    name: str
    zone_type: DeploymentZoneType
    # Define zone as a polygon with vertices (x, y) coordinates
    vertices: List[Tuple[float, float]]
    cutouts: Optional[List[ZoneCutout]] = None  # Areas to cut out from this zone
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is inside this deployment zone using ray casting algorithm."""
        # First check if point is within the main polygon
        n = len(self.vertices)
        inside = False
        
        p1x, p1y = self.vertices[0]
        for i in range(1, n + 1):
            p2x, p2y = self.vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        # If point is inside the main polygon, check if it's in any cutout areas
        if inside and self.cutouts:
            for cutout in self.cutouts:
                if cutout.contains_point(x, y):
                    return False  # Point is in a cutout, so not in deployment zone
        
        return inside
    
    def contains_circular_base(self, center_x: float, center_y: float, radius: float) -> bool:
        """Check if a circular model base is wholly within this deployment zone."""
        # For a circle to be wholly within the zone:
        # 1. The center must be in the zone
        # 2. All points on the circle's circumference must be in the zone
        # 3. None of the circle should intersect with any cutouts
        
        # Quick check: if center is not in zone, circle can't be wholly in zone
        if not self.contains_point(center_x, center_y):
            return False
        
        # Check multiple points around the circumference (more accurate than just edge points)
        num_check_points = 16  # Check 16 points around the circle
        for i in range(num_check_points):
            angle = 2 * math.pi * i / num_check_points
            edge_x = center_x + radius * math.cos(angle)
            edge_y = center_y + radius * math.sin(angle)
            
            if not self.contains_point(edge_x, edge_y):
                return False
        
        return True
    
    def contains_polygon_base(self, vertices: List[Tuple[float, float]]) -> bool:
        """Check if a polygonal model base is wholly within this deployment zone."""
        # For a polygon to be wholly within the zone:
        # 1. All vertices must be in the zone
        # 2. All edges should not intersect zone boundaries (complex check)
        # For simplicity, we'll check all vertices and some intermediate points
        
        # Check all vertices
        for x, y in vertices:
            if not self.contains_point(x, y):
                return False
        
        # Check midpoints of all edges for better coverage
        for i in range(len(vertices)):
            x1, y1 = vertices[i]
            x2, y2 = vertices[(i + 1) % len(vertices)]
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            
            if not self.contains_point(mid_x, mid_y):
                return False
        
        return True


@dataclass
class MissionObjectiveMarker:
    """Represents an objective marker placement."""
    x: float
    y: float
    z: float = 0.0
    control_radius: float = 3.0
    name: str = "Objective Marker"


class OfficialMission:
    """Base class for official Warhammer 40k missions."""
    
    def __init__(self, name: str, battlefield_width: float = 60.0, battlefield_height: float = 44.0):
        self.name = name
        self.battlefield_width = battlefield_width
        self.battlefield_height = battlefield_height
        self.deployment_zones: List[DeploymentZone] = []
        self.objective_markers: List[MissionObjectiveMarker] = []
        
        # Center coordinates for reference
        self.center_x = battlefield_width / 2.0  # 30"
        self.center_y = battlefield_height / 2.0  # 22"
    
    def get_deployment_zones(self) -> List[DeploymentZone]:
        """Get all deployment zones for this mission."""
        return self.deployment_zones
    
    def get_objective_markers(self) -> List[MissionObjectiveMarker]:
        """Get all objective marker placements for this mission."""
        return self.objective_markers
    
    def get_defender_zones(self) -> List[DeploymentZone]:
        """Get zones available to the defender."""
        return [zone for zone in self.deployment_zones if zone.zone_type == DeploymentZoneType.DEFENDER]
    
    def get_attacker_zones(self) -> List[DeploymentZone]:
        """Get zones available to the attacker."""
        return [zone for zone in self.deployment_zones if zone.zone_type == DeploymentZoneType.ATTACKER]


class CrucibleOfBattle(OfficialMission):
    """
    Crucible of Battle mission from Chapter Approved 2025/2026.
    
    Based on the official deployment map:
    - 60" x 44" battlefield
    - Defender (Green): Bottom-left triangular corner
    - Attacker (Red): Top-right triangular corner
    - Objectives: 5 markers in specific positions including center
    """
    
    def __init__(self):
        super().__init__("Crucible of Battle")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        """Setup deployment zones based on Crucible of Battle layout."""
        
        # Defender zones (Green) 
        defender_vertices = [
            (0, 0),      # Top-left corner
            (30, 44),    # Bottom-middle
            (0, 44),     # Bottom-left corner
        ]
        
        # Attacker zones (Red)
        attacker_vertices = [
            (30, 0),    # Top-middle
            (60, 0),    # Top-right corner
            (60, 44),   # Bottom-right corner
        ]
        
        self.deployment_zones = [
            DeploymentZone("Defender", DeploymentZoneType.DEFENDER, defender_vertices),
            DeploymentZone("Attacker", DeploymentZoneType.ATTACKER, attacker_vertices),
        ]
    
    def _setup_objectives(self):
        """Setup objective markers based on Crucible of Battle layout."""
        
        # Based on skull markers in the image:
        # Center objective (30", 22")
        center_objective = MissionObjectiveMarker(
            x=30.0, y=22.0, name="Center Objective"
        )
        
        # Four corner objectives positioned 12" from edges
        # Bottom-left area (defender side)
        bl_objective = MissionObjectiveMarker(
            x=14.0, y=34.0, name="Southwest Objective"
        )
        
        # Top-right area (attacker side)  
        tr_objective = MissionObjectiveMarker(
            x=46.0, y=10.0, name="Northeast Objective"
        )
        
        # Top-left area (No Mans Land)
        tl_objective = MissionObjectiveMarker(
            x=20.0, y=8.0, name="Northwest Objective"
        )
        
        # Bottom-right area (No Mans Land)
        br_objective = MissionObjectiveMarker(
            x=40.0, y=36.0, name="Southeast Objective"
        )
        
        self.objective_markers = [
            center_objective,
            bl_objective,
            tr_objective, 
            tl_objective,
            br_objective
        ]


class DawnOfWar(OfficialMission):
    """Dawn of War mission - standard opposed deployment."""
    
    def __init__(self):
        super().__init__("Dawn of War")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        """Standard 18" deployment zones from opposite table edges."""
        
        # Attacker zone (Red) - Left 18" 
        attacker_vertices = [
            (0, 0),      # Top-left
            (60, 0),     # Top-Right
            (60, 12),    # 12" down on right edge
            (0, 12),     # 12" down on left edge
        ]
        
        # Defender zone (Green) - Right 18"
        defender_vertices = [
            (0, 32),     # 12" up on left edge
            (60, 32),    # 12" up on right edge
            (60, 44),    # Bottom-Right
            (0, 44),     # Bottom-Left
        ]
        
        self.deployment_zones = [
            DeploymentZone("Defender Zone", DeploymentZoneType.DEFENDER, defender_vertices),
            DeploymentZone("Attacker Zone", DeploymentZoneType.ATTACKER, attacker_vertices),
        ]
    
    def _setup_objectives(self):
        """Standard objective placement for Dawn of War."""
        
        # Center objective
        center = MissionObjectiveMarker(x=30.0, y=22.0, name="Center Objective")
        
        # Left and right objectives  
        left = MissionObjectiveMarker(x=10.0, y=22.0, name="West Objective")
        right = MissionObjectiveMarker(x=50.0, y=22.0, name="East Objective")

        # Top and bottom objectives
        bottom = MissionObjectiveMarker(x=30.0, y=38.0, name="Bottom Objective")
        top = MissionObjectiveMarker(x=30.0, y=6.0, name="Top Objective")
        
        self.objective_markers = [center, left, right, top, bottom]


class HammerAndAnvil(OfficialMission):
    """Hammer and Anvil mission - opposed deployment from short edges."""
    
    def __init__(self):
        super().__init__("Hammer and Anvil")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        """18" deployment zones from opposite short table edges."""
        
        # Defender zone (Green) - Left 18" rectangle
        defender_vertices = [
            (0, 0),      # Bottom-left
            (0, 44),     # Top-left
            (18, 44),    # Top-right of defender zone
            (18, 0),     # Bottom-right of defender zone
        ]
        
        # Attacker zone (Red) - Right 18" rectangle (mirrored)
        attacker_vertices = [
            (42, 0),     # Bottom-left of attacker zone
            (42, 44),    # Top-left of attacker zone
            (60, 44),    # Top-right
            (60, 0),     # Bottom-right
        ]
        
        self.deployment_zones = [
            DeploymentZone("Defender Zone", DeploymentZoneType.DEFENDER, defender_vertices),
            DeploymentZone("Attacker Zone", DeploymentZoneType.ATTACKER, attacker_vertices),
        ]
    
    def _setup_objectives(self):
        """Five objectives in cross pattern for Hammer and Anvil."""
        
        # Center objective
        center = MissionObjectiveMarker(x=30.0, y=22.0, name="Center Objective")
        
        # Four cardinal direction objectives
        bottom = MissionObjectiveMarker(x=30.0, y=38.0, name="South Objective")
        top = MissionObjectiveMarker(x=30.0, y=6.0, name="North Objective")
        left = MissionObjectiveMarker(x=10.0, y=22.0, name="West Objective")
        right = MissionObjectiveMarker(x=50.0, y=22.0, name="East Objective")
        
        self.objective_markers = [center, top, bottom, left, right]


class TippingPoint(OfficialMission):
    """Tipping Point mission."""
    
    def __init__(self):
        super().__init__("Tipping Point")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        """Tipping Point deployment zones."""

        defender_vertices = [
            (0, 0), (12, 0), (12, 22), (20, 22), (20, 44), (0, 44)
        ]
        attacker_vertices = [
            (40, 0), (60, 0), (60, 44), (48, 44), (48, 22), (40, 22)
        ]
        
        self.deployment_zones = [
            DeploymentZone("Defender Zone", DeploymentZoneType.DEFENDER, defender_vertices),
            DeploymentZone("Attacker Zone", DeploymentZoneType.ATTACKER, attacker_vertices),
        ]
    
    def _setup_objectives(self):
        """Tipping Point objectives."""
        # Center objective
        center = MissionObjectiveMarker(x=30.0, y=22.0, name="Center Objective")
        
        # Four cardinal direction objectives
        nw = MissionObjectiveMarker(x=22.0, y=8.0, name="Northwest Objective")
        ne = MissionObjectiveMarker(x=46.0, y=10.0, name="Northeast Objective")
        sw = MissionObjectiveMarker(x=14.0, y=34.0, name="Southwest Objective")
        se = MissionObjectiveMarker(x=38.0, y=36.0, name="Southeast Objective")
        
        self.objective_markers = [center, nw, ne, sw, se]


class SearchAndDestroy(OfficialMission):
    """Search and Destroy mission - deployment zones to be implemented."""
    
    def __init__(self):
        super().__init__("Search and Destroy")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        """Search and Destroy deployment zones with central circular cutout."""
        # Create the 9" radius circular cutout at the center point
        center_cutout = ZoneCutout(
            cutout_type=CutoutType.CIRCLE,
            center_x=30.0,
            center_y=22.0,
            parameters=9.0  # 9" radius
        )
        
        # Defender gets the entire top half of battlefield (y > 22)
        defender_vertices = [
            (0, 22.01), (60, 22.01), (60, 44), (0, 44)
        ]
        # Attacker gets the entire bottom half of battlefield (y < 22)  
        attacker_vertices = [
            (0, 0), (60, 0), (60, 21.99), (0, 21.99)
        ]
        
        self.deployment_zones = [
            DeploymentZone("Defender Zone", DeploymentZoneType.DEFENDER, defender_vertices, [center_cutout]),
            DeploymentZone("Attacker Zone", DeploymentZoneType.ATTACKER, attacker_vertices, [center_cutout]),
        ]
    
    def _setup_objectives(self):
        """Search and Destroy objectives."""
        # Center objective
        center = MissionObjectiveMarker(x=30.0, y=22.0, name="Center Objective")
        
        # Four cardinal direction objectives
        nw = MissionObjectiveMarker(x=14.0, y=10.0, name="Northwest Objective")
        ne = MissionObjectiveMarker(x=46.0, y=10.0, name="Northeast Objective")
        sw = MissionObjectiveMarker(x=14.0, y=34.0, name="Southwest Objective")
        se = MissionObjectiveMarker(x=46.0, y=34.0, name="Southeast Objective")
        
        self.objective_markers = [center, nw, ne, sw, se]


class SweepingEngagement(OfficialMission):
    """Sweeping Engagement mission."""
    
    def __init__(self):
        super().__init__("Sweeping Engagement")
        self._setup_deployment_zones()
        self._setup_objectives()
    
    def _setup_deployment_zones(self):
        """Sweeping Engagement deployment zones."""
        defender_vertices = [
            (0, 30), (30, 30), (30, 36), (60, 36), (60, 44), (0, 44)
        ]
        attacker_vertices = [
            (0, 0), (60, 0), (60, 14), (30, 14), (30, 8), (0, 8)
        ]
        
        self.deployment_zones = [
            DeploymentZone("Defender Zone", DeploymentZoneType.DEFENDER, defender_vertices),
            DeploymentZone("Attacker Zone", DeploymentZoneType.ATTACKER, attacker_vertices),
        ]
    
    def _setup_objectives(self):
        """Sweeping Engagement objectives."""
        # Center objective
        center = MissionObjectiveMarker(x=30.0, y=22.0, name="Center Objective")
        
        # Four cardinal direction objectives
        nw = MissionObjectiveMarker(x=10.0, y=18.0, name="Northwest Objective")
        ne = MissionObjectiveMarker(x=42.0, y=6.0, name="Northeast Objective")
        sw = MissionObjectiveMarker(x=18.0, y=38.0, name="Southwest Objective")
        se = MissionObjectiveMarker(x=50.0, y=26.0, name="Southeast Objective")
        
        self.objective_markers = [center, nw, ne, sw, se]


class MissionRegistry:
    """Registry of all available official missions."""
    
    _missions = {
        "Crucible of Battle": CrucibleOfBattle,
        "Dawn of War": DawnOfWar,
        "Hammer and Anvil": HammerAndAnvil,
        "Tipping Point": TippingPoint,
        "Search and Destroy": SearchAndDestroy,
        "Sweeping Engagement": SweepingEngagement,
    }
    
    @classmethod
    def get_mission(cls, mission_name: str) -> OfficialMission:
        """Get a mission instance by name."""
        if mission_name not in cls._missions:
            raise ValueError(f"Mission '{mission_name}' not found. Available: {list(cls._missions.keys())}")
        
        return cls._missions[mission_name]()
    
    @classmethod
    def get_available_missions(cls) -> List[str]:
        """Get list of all available mission names."""
        return list(cls._missions.keys())
    
    @classmethod
    def register_mission(cls, name: str, mission_class):
        """Register a new mission type."""
        cls._missions[name] = mission_class


def create_objectives_from_mission(mission: OfficialMission, game_state=None) -> List[Objective]:
    """Convert mission objective markers into game objectives."""
    objectives = []
    
    for i, marker in enumerate(mission.get_objective_markers()):
        objective_point = ObjectivePoint(
            x=marker.x,
            y=marker.y, 
            z=marker.z,
            control_radius=marker.control_radius
        )
        
        # Create simple control objective
        objective = Objective(
            name=marker.name,
            category=ObjectiveCategory.PRIMARY,
            points=5,  # Standard points per objective
            description=f"Control {marker.name} to score points",
            conditions=lambda game, point=objective_point: point.controlling_player is not None,
            location=objective_point
        )
        
        objectives.append(objective)
    
    return objectives
