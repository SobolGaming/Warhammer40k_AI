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
    circ = Point(center).buffer(1, resolution=64)
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
        # Calculate the distance between two models using their bases
        # Note: we round to 2 decimal precision (we can increase that if necessary)
        delta_x = other.x - self.x
        delta_y = other.y - self.y
        angle = get_angle(delta_y, delta_x)
        if self.z == other.z:
            return max(0, round(
                get_dist(delta_x, delta_y)
                - self.get_radius(angle)
                - other.get_radius(angle)
            , 2))
        elif self.z + self.model_height < other.z:
            xy_dist = max(0,
                get_dist(delta_x, delta_y)
                - self.get_radius(angle)
                - other.get_radius(angle)
            )
            return get_dist(xy_dist, other.z - self.z - self.model_height)
        elif other.z + other.model_height < self.z:
            xy_dist = max(0,
                get_dist(delta_x, delta_y)
                - self.get_radius(angle)
                - other.get_radius(angle)
            )
            return round(get_dist(xy_dist, self.z - other.z - other.model_height), 2)
        # otherwise treat it the same as if on the same z-axis since parts of the model overlap in the z-space
        else:
            return max(0, round(
                get_dist(delta_x, delta_y)
                - self.get_radius(angle)
                - other.get_radius(angle)
            , 2))

    def vertical_distance(self, other: 'Base') -> float:
        """Calculate the distance between two models in vertical space."""
        if self.z + self.model_height < other.z:
            return round(other.z - self.z - self.model_height, 2)
        elif other.z + other.model_height < self.z:
            return round(self.z - other.z - other.model_height, 2)
        else:
            return 0.0

    def collides_with(self, other: 'Base') -> bool:
        print(f"Base 1: {self.x:.2f}, {self.y:.2f}, {self.z:.2f}, {self.facing:.2f}")
        print(f"Base 2: {other.x:.2f}, {other.y:.2f}, {other.z:.2f}, {other.facing:.2f}")
        vert_dist = self.vertical_distance(other)
        edge_dist = self.edge_to_edge_distance(other)
        print(f"Vertical Distance: {vert_dist}, Edge Distance: {edge_dist}")
        return vert_dist == 0.0 and edge_dist == 0.0

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