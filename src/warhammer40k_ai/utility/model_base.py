import logging
import typing
import math
from enum import Enum
from shapely.geometry import Point, Polygon as Poly
from shapely import affinity
from warhammer40k_ai.utility.calcs import get_dist, get_angle

logger = logging.getLogger(__name__)

# Constants
DEGREES_IN_CIRCLE = 360
RADIANS_IN_CIRCLE = 2 * math.pi

# Create a shapely ellipse
def create_ellipse(center: typing.Tuple[float, float], lengths: typing.Tuple[float, float], bearing: float = 0) -> Poly:
    """
    Create a shapely ellipse.
    
    :param center: The center point of the ellipse (x, y)
    :param lengths: The lengths of the ellipse axes (on x-axis, on y-axis)
    :param bearing: The rotation of the ellipse in radians
    :return: A shapely Polygon representing the ellipse
    """
    circ = Point(center).buffer(1, quad_segs=64)
    ell = affinity.scale(circ, lengths[0], lengths[1])
    return affinity.rotate(ell, math.degrees(bearing))

# Create a shapely rectangle
def create_rectangle(center: typing.Tuple[float, float], lengths: typing.Tuple[float, float], bearing: float = 0) -> Poly:
    """
    Create a shapely rectangle.
    
    :param center: The center point of the rectangle (x, y)
    :param lengths: The lengths of the rectangle sides (width, height)
    :param bearing: The rotation of the rectangle in radians
    :return: A shapely Polygon representing the rectangle
    """
    start = Point(center)
    width, height = lengths[0], lengths[1]
    points = [
        (start.x + width, start.y + height),
        (start.x + width, start.y - height),
        (start.x - width, start.y - height),
        (start.x - width, start.y + height),
    ]
    rect = Poly(points)
    return affinity.rotate(rect, math.degrees(bearing))

class BaseType(Enum):
    CIRCULAR = 1
    ELLIPTICAL = 2
    HULL = 3

class Base:
    def __init__(self, base_type: BaseType, radius: typing.Union[float, typing.Tuple[float, float]]) -> None:
        """
        Initialize a Base object.
        
        :param base_type: The type of the base (CIRCULAR, ELLIPTICAL, or HULL)
        :param radius: The radius (or radii) of the base
        """
        self.x: float = 0.0
        self.y: float = 0.0
        self.z: float = 0.0
        self.facing: float = 0.0
        self.base_type = base_type
        self.radius: typing.Tuple[float, float] = self._normalize_radius(radius)
        self.set_model_height()

    def _normalize_radius(self, radius: typing.Union[float, typing.Tuple[float, float]]) -> typing.Tuple[float, float]:
        if isinstance(radius, (float, int)):
            return (float(radius), float(radius))
        elif isinstance(radius, tuple) and len(radius) == 2:
            return (float(radius[0]), float(radius[1]))
        else:
            raise ValueError("Invalid radius format. Expected float or tuple of two floats.")

    def set_model_height(self, height: float = None) -> None:
        self.model_height = min(self.radius) * 2.0 if height is None else height

    def set_facing(self, facing: float) -> None:
        # Normalize facing to be between 0 and 2π radians
        self.facing = facing % RADIANS_IN_CIRCLE

    def set_x(self, x: float) -> None:
        self.x = x

    def set_y(self, y: float) -> None:
        self.y = y

    def set_z(self, z: float) -> None:
        self.z = z

    def set_position(self, x: float, y: float, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z

    @property
    def has_circular_base(self) -> bool:
        return self.base_type == BaseType.CIRCULAR

    @property
    def base_size(self) -> float:
        return max(self.radius[0], self.radius[1])

    def get_radius(self, angle: float = 0.0) -> float:
        if self.base_type == BaseType.CIRCULAR:
            return round(self.radius[0], 4)
        elif self.base_type == BaseType.ELLIPTICAL:
            return self._get_elliptical_radius(angle)
        elif self.base_type == BaseType.HULL:
            return self._get_hull_radius(angle)
        else:
            raise ValueError(f"Unknown base_type: {self.base_type}")

    def _get_elliptical_radius(self, angle: float) -> float:
        # Ensure angle is relative to the major axis
        relative_angle = angle - self.facing
        a, b = self.radius  # a is the semi-major axis, b is the semi-minor axis
        return round((a * b) / math.sqrt((b * math.cos(relative_angle))**2 + (a * math.sin(relative_angle))**2), 4)

    def _get_hull_radius(self, angle: float) -> float:
        major_axis, minor_axis = self.radius[1], self.radius[0]
        full_angle = (math.pi - self.facing) + angle
        corner_angle = math.atan(major_axis/minor_axis)
        
        if (full_angle >= -corner_angle and full_angle < corner_angle) or \
           (full_angle >= (math.pi - corner_angle) and full_angle <(math.pi + corner_angle)):
            dx = minor_axis
            dy = dx * math.tan(full_angle)
        else:
            dx = major_axis / math.tan(full_angle)
            dy = major_axis
        
        radius = math.hypot(dx, dy)
        assert radius > 0, "bad HULL radius calculation"
        return round(radius, 4)

    # Determine the longest distance to parameter point of base
    def get_longest_radius(self) -> float:
        if hasattr(self, 'longest_radius'):
            return self.longest_radius
        if self.base_type in [BaseType.CIRCULAR, BaseType.ELLIPTICAL]:
            self.longest_radius = max(self.radius)
            return self.longest_radius
        elif self.base_type == BaseType.HULL:
            self.longest_radius = math.hypot(self.radius[0], self.radius[1])
            return self.longest_radius
        else:
            raise ValueError(f"Unknown base_type: {self.base_type}")

    # Get the geometric shape of the base
    def get_base_shape(self) -> Poly:
        if self.base_type in [BaseType.CIRCULAR, BaseType.ELLIPTICAL]:
            return create_ellipse((self.x, self.y), self.radius, self.facing)
        elif self.base_type == BaseType.HULL:
            return create_rectangle((self.x, self.y), self.radius, self.facing)
        else:
            raise ValueError(f"Unknown BaseType geometry: {self.base_type}")

    def get_base_shape_at(self, x: float, y: float, facing: float) -> Poly:
        if self.base_type in [BaseType.CIRCULAR, BaseType.ELLIPTICAL]:
            return create_ellipse((x, y), self.radius, facing)
        elif self.base_type == BaseType.HULL:
            return create_rectangle((x, y), self.radius, facing)
        else:
            raise ValueError(f"Unknown BaseType geometry: {self.base_type}")

    ### Measurement functions
    def edge_to_edge_distance(self, other: 'Base') -> float:
        # --- 2D distance via Shapely ---
        # true minimal distance between the two rotated polygons
        base_shape = self.get_base_shape()
        other_base_shape = other.get_base_shape()

        xy_dist = base_shape.distance(other_base_shape)

        # --- vertical separation ---
        top_z = self.z + self.model_height
        other_top = other.z + other.model_height

        if top_z < other.z:
            dz = other.z - top_z
        elif other_top < self.z:
            dz = self.z - other_top
        else:
            dz = 0.0

        # --- combine and round once at the end ---
        return round(get_dist(xy_dist, dz), 2)

    def coherency_distance(self, other: 'Base') -> float:
        """
        Calculate coherency distance using Warhammer 40k rules:
        - 2" horizontal distance (base-to-base)
        - 5" vertical distance (base-to-base)

        Returns the minimum distance for coherency purposes.
        """
        # Get 2D distance between bases
        base_shape = self.get_base_shape()
        other_base_shape = other.get_base_shape()
        horizontal_dist = base_shape.distance(other_base_shape)

        # Get vertical distance between base centers (not including model height)
        vertical_dist = abs(self.z - other.z)

        # Check coherency rules:
        # - If horizontal distance <= 2", models are coherent regardless of vertical distance up to 5"
        # - If vertical distance <= 5", models are coherent regardless of horizontal distance up to 2"

        if horizontal_dist <= 2.0 and vertical_dist <= 5.0:
            return 0.0  # In coherency
        elif horizontal_dist <= 2.0:
            return vertical_dist - 5.0  # Vertical distance beyond 5"
        elif vertical_dist <= 5.0:
            return horizontal_dist - 2.0  # Horizontal distance beyond 2"
        else:
            # Both distances exceed limits - return the smaller excess
            horizontal_excess = horizontal_dist - 2.0
            vertical_excess = vertical_dist - 5.0
            return min(horizontal_excess, vertical_excess)


    def vertical_distance(self, other: 'Base') -> float:
        """Calculate the distance between two models in vertical space."""
        if self.z + self.model_height < other.z:
            return round(other.z - self.z - self.model_height, 2)
        elif other.z + other.model_height < self.z:
            return round(self.z - other.z - other.model_height, 2)
        else:
            return 0.0

    def collides_with(self, other: 'Base') -> bool:
        """
        Check if two model bases collide with 3D optimization.

        Optimization strategy:
        1. Fast 2D check first - if no 2D overlap, no collision
        2. If 2D overlap exists - check Z positions
        3. If Z positions differ - do detailed 3D collision check based on model heights
        """
        #print(f"Base 1: {self.x:.2f}, {self.y:.2f}, {self.z:.2f}, {self.facing:.2f}")
        #print(f"Base 2: {other.x:.2f}, {other.y:.2f}, {other.z:.2f}, {other.facing:.2f}")

        # Step 1: Fast 2D check - if no 2D overlap, no collision possible
        edge_dist = self.edge_to_edge_distance(other)
        if edge_dist > 0.0:
            return False  # No 2D overlap, no collision

        # Step 2: 2D overlap exists - check Z positions
        z_diff = abs(self.z - other.z)

        # If Z positions are the same (or very close), there's definitely a collision
        if z_diff < 0.1:  # Within 0.1" is considered same level
            return True

        # Step 3: Different Z levels - check if vertical separation is sufficient
        # Calculate the minimum Z separation needed to avoid collision
        # Models need to be separated by at least the height of the taller model
        min_z_separation = max(self.model_height, other.model_height)

        # If Z separation is sufficient, no collision
        if z_diff >= min_z_separation:
            return False

        # Z separation is insufficient - models collide
        return True

    #########################################################################################
    ### Dunder methods
    #########################################################################################
    def __repr__(self) -> str:
        return f"Base(type={self.base_type.name}, radius={self.radius}, x={self.x}, y={self.y}, z={self.z}, facing={self.facing})"

    def __str__(self) -> str:
        base_type_str = self.base_type.name.capitalize()
        radius_str = f"{self.radius[0]}" if self.radius[0] == self.radius[1] else f"{self.radius[0]}x{self.radius[1]}"
        return f"{base_type_str} base at ({self.x:.2f}, {self.y:.2f}, {self.z:.2f}), facing {math.degrees(self.facing):.1f}°, radius: {radius_str}"


if __name__ == "__main__":
    b = Base(BaseType.CIRCULAR, 32)
    val = b.get_radius()
    print(f"Radius: {val}")
    assert val == 32.0

    b = Base(BaseType.ELLIPTICAL, (60, 35))
    val = b.get_radius(math.radians(90))
    print(f"Radius: {val}")
    assert val == 35.0

    val = b.get_radius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 42.7549

    b.set_facing(math.radians(90))
    val = b.get_radius(math.radians(90))
    print(f"Radius: {val}")
    assert val == 60.0

    b.set_facing(math.radians(315))
    val = b.get_radius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 35.0

    b.set_facing(math.radians(135))
    val = b.get_radius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 35.0

    b.set_facing(math.radians(315))
    val = b.get_radius(math.radians(0))
    print(f"Radius: {val}")
    assert val == 42.7549

    base_1 = Base(BaseType.ELLIPTICAL, (10, 5))
    base_1.set_position(10, 0)
    base_2 = Base(BaseType.ELLIPTICAL, (10, 5))
    base_2.set_position(40, 0)
    dist = base_1.edge_to_edge_distance(base_2)
    print(f"Distance: {dist}")
    assert dist == 10.0

    base_1.set_facing(math.radians(45))
    dist = base_1.edge_to_edge_distance(base_2)
    print(f"Distance: {dist}")
    assert not dist == 10.0
    assert dist == 13.68

    base_1.set_position(40, 0, 20)
    vert_dist = base_1.vertical_distance(base_2)
    dist = base_1.edge_to_edge_distance(base_2)
    print(f"Vertical Distance: {vert_dist}")
    assert vert_dist == 10.0
    print(f"Distance: {dist}")
    assert dist == 10.0

    base_1.set_position(10, 0, 20)
    base_1.set_facing(math.radians(0))
    vert_dist = base_1.vertical_distance(base_2)
    dist = base_1.edge_to_edge_distance(base_2)
    print(f"Vertical Distance: {vert_dist}")
    assert vert_dist == 10.0
    print(f"Distance: {dist}")
    assert dist == 14.14