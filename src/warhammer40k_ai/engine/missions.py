"""
Official Warhammer 40k 10th Edition Mission Deployment Zones and Objectives
Based on Chapter Approved 2025/2026 mission layouts.

Battlefield dimensions: 60" horizontal x 44" vertical
Coordinate system: (0,0) at top-left corner, (60,44) at bottom-right corner
"""

from typing import List, Dict, Tuple, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
import uuid
from ..battlefield.map import ObjectivePoint, Objective, ObjectiveCategory
import math
from shapely.geometry import Point, Polygon as ShapelyPolygon


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
        point = Point(x, y)
        cutout_geometry = self.get_shapely_geometry()
        return cutout_geometry.contains(point)
    
    def get_shapely_geometry(self):
        """Get the Shapely geometry representation of this cutout."""
        if self.cutout_type == CutoutType.CIRCLE:
            radius = self.parameters
            return Point(self.center_x, self.center_y).buffer(radius)
        
        elif self.cutout_type == CutoutType.RECTANGLE:
            width, height = self.parameters
            half_width = width / 2
            half_height = height / 2
            vertices = [
                (self.center_x - half_width, self.center_y - half_height),
                (self.center_x + half_width, self.center_y - half_height),
                (self.center_x + half_width, self.center_y + half_height),
                (self.center_x - half_width, self.center_y + half_height)
            ]
            return ShapelyPolygon(vertices)
        
        elif self.cutout_type == CutoutType.POLYGON:
            # Convert relative vertices to absolute coordinates
            vertices = [(self.center_x + dx, self.center_y + dy) for dx, dy in self.parameters]
            return ShapelyPolygon(vertices)
        
        return None
    
    def intersects_circular_base(self, center_x: float, center_y: float, radius: float) -> bool:
        """Check if a circular model base has positive-area overlap with this cutout.
        Tangential contact (touching boundary) is allowed and should not count as intersecting."""
        base_geometry = Point(center_x, center_y).buffer(radius)
        cutout_geometry = self.get_shapely_geometry()
        intersection = cutout_geometry.intersection(base_geometry)
        return getattr(intersection, 'area', 0.0) > 1e-6
    
    def intersects_polygon_base(self, vertices: List[Tuple[float, float]]) -> bool:
        """Check if a polygonal model base has positive-area overlap with this cutout.
        Tangential contact (touching boundary) is allowed and should not count as intersecting."""
        base_geometry = ShapelyPolygon(vertices)
        cutout_geometry = self.get_shapely_geometry()
        intersection = cutout_geometry.intersection(base_geometry)
        return getattr(intersection, 'area', 0.0) > 1e-6
    

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
        """Check if a circular model base is wholly within this deployment zone.
        Accepts scalar or vector-like radius; coerces to a single float."""
        # Coerce radius to float to avoid vectorized buffer producing arrays
        r = radius
        try:
            r = float(r)
        except Exception:
            try:
                # If tuple/list/ndarray, use the max component as effective radius
                r = float(max(r))
            except Exception:
                # Last resort
                r = float(r)

        # Create Shapely geometry for the model base
        base_geometry = Point(center_x, center_y).buffer(r)
        
        # Create Shapely geometry for the deployment zone
        zone_geometry = ShapelyPolygon(self.vertices)
        if not getattr(zone_geometry, 'is_valid', True):
            zone_geometry = zone_geometry.buffer(0)
        
        # Base must be wholly within the zone (allow touching boundary, tolerate epsilon)
        if not zone_geometry.buffer(1e-3).covers(base_geometry):
            return False
        
        # Base must not intersect with any cutouts
        if self.cutouts:
            for cutout in self.cutouts:
                if cutout.intersects_circular_base(center_x, center_y, r):
                    return False
        
        return True
    
    def contains_polygon_base(self, vertices: List[Tuple[float, float]], center: Tuple[float, float] = None, radii: Tuple[float, float] = None, facing: float = 0.0) -> bool:
        """Check if a non-circular base is wholly within this zone.
        If center/radii provided (elliptical), build analytic ellipse to avoid vertex artifacts; otherwise fallback to polygon.
        Allows boundary contact and ignores tangential contact with cutouts."""
        from shapely.geometry import Point as _ShPoint
        from shapely.affinity import scale as _sh_scale, rotate as _sh_rotate

        if center is not None and radii is not None:
            cx, cy = center
            a, b = radii  # semi-major, semi-minor
            try:
                ellipse = _sh_scale(_ShPoint(cx, cy).buffer(1.0), a, b)
                if facing:
                    ellipse = _sh_rotate(ellipse, math.degrees(facing), origin=(cx, cy))
                base_geometry = ellipse
            except Exception:
                base_geometry = ShapelyPolygon(vertices)
        else:
            base_geometry = ShapelyPolygon(vertices)
        if not getattr(base_geometry, 'is_valid', True):
            base_geometry = base_geometry.buffer(0)
        zone_geometry = ShapelyPolygon(self.vertices)
        if not getattr(zone_geometry, 'is_valid', True):
            zone_geometry = zone_geometry.buffer(0)

        # Allow boundary contact
        if not zone_geometry.covers(base_geometry):
            return False

        # Disallow positive-area overlap with cutouts; allow boundary tangency
        if self.cutouts:
            for cutout in self.cutouts:
                cg = cutout.get_shapely_geometry()
                if cg is None:
                    continue
                # Clean cutout geometry if needed
                if hasattr(cg, 'is_valid') and not cg.is_valid:
                    cg = cg.buffer(0)
                inter = cg.intersection(base_geometry)
                if getattr(inter, 'area', 0.0) > 1e-6:
                    return False

        return True

    def contains_base_geometry(self, base_geometry) -> bool:
        """General-purpose check using a provided Shapely geometry for the base.
        Allows boundary contact for zone; forbids positive-area overlap with cutouts.
        """
        # Clean inputs if needed
        if hasattr(base_geometry, 'is_valid') and not base_geometry.is_valid:
            base_geometry = base_geometry.buffer(0)

        zone_geometry = ShapelyPolygon(self.vertices)
        if not getattr(zone_geometry, 'is_valid', True):
            zone_geometry = zone_geometry.buffer(0)

        # Allow tiny tolerance and boundary contact
        if not zone_geometry.buffer(1e-3).covers(base_geometry):
            return False

        if self.cutouts:
            for cutout in self.cutouts:
                cg = cutout.get_shapely_geometry()
                if cg is None:
                    continue
                if hasattr(cg, 'is_valid') and not cg.is_valid:
                    cg = cg.buffer(0)
                inter = cg.intersection(base_geometry)
                if getattr(inter, 'area', 0.0) > 1e-6:
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
    marker_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def id(self) -> str:
        return self.marker_id


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
        
        # Defender
        defender_vertices = [
            (0, 22), (30, 22), (30, 44), (0, 44)
        ]
        # Attacker 
        attacker_vertices = [
            (30, 0), (60, 0), (60, 22), (30, 22)
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
