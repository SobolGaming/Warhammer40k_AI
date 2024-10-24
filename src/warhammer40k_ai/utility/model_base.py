import logging
import typing
import math
from enum import Enum
from shapely.geometry import Point, Polygon as Poly
from shapely import affinity

logger = logging.getLogger(__name__)

# Constants
DEGREES_IN_CIRCLE = 360
RADIANS_IN_CIRCLE = 2 * math.pi

# Create a shapely ellipse
def create_ellipse(center: typing.Tuple[float, float], lengths: typing.Tuple[float, float], bearing: float = 0) -> Poly:
    """
    Create a shapely ellipse.
    
    :param center: The center point of the ellipse (x, y)
    :param lengths: The lengths of the ellipse axes (major, minor)
    :param bearing: The rotation of the ellipse in radians
    :return: A shapely Polygon representing the ellipse
    """
    circ = Point(center).buffer(1, resolution=64)
    ell = affinity.scale(circ, lengths[1], lengths[0])
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
    width, height = lengths[1], lengths[0]
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
        #if self.base_type == BaseType.ELLIPTICAL:
        #    # Swap major and minor axes if necessary to keep major axis aligned with facing
        #    if abs(math.cos(facing)) < abs(math.sin(facing)):
        #        self.radius = (self.radius[1], self.radius[0])

    @property
    def has_circular_base(self) -> bool:
        return self.base_type == BaseType.CIRCULAR

    @property
    def base_size(self) -> float:
        return self.radius[0]

    def getRadius(self, angle: float = 0.0) -> float:
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
    def longestDistance(self) -> float:
        if self.base_type in [BaseType.CIRCULAR, BaseType.ELLIPTICAL]:
            return max(self.radius)
        elif self.base_type == BaseType.HULL:
            return math.hypot(self.radius[0], self.radius[1])
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

    def __repr__(self) -> str:
        return f"Base(type={self.base_type.name}, radius={self.radius}, x={self.x}, y={self.y}, z={self.z}, facing={self.facing})"

    def __str__(self) -> str:
        base_type_str = self.base_type.name.capitalize()
        radius_str = f"{self.radius[0]}" if self.radius[0] == self.radius[1] else f"{self.radius[0]}x{self.radius[1]}"
        return f"{base_type_str} base at ({self.x:.2f}, {self.y:.2f}, {self.z:.2f}), facing {math.degrees(self.facing):.1f}°, radius: {radius_str}"

if __name__ == "__main__":
    b = Base(BaseType.CIRCULAR, 32)
    val = b.getRadius()
    print(f"Radius: {val}")
    assert val == 32.0

    b = Base(BaseType.ELLIPTICAL, (60, 35))
    val = b.getRadius(math.radians(90))
    print(f"Radius: {val}")
    assert val == 35.0

    val = b.getRadius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 42.7549

    b.set_facing(math.radians(90))
    val = b.getRadius(math.radians(90))
    print(f"Radius: {val}")
    assert val == 60.0

    b.set_facing(math.radians(315))
    val = b.getRadius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 35.0

    b.set_facing(math.radians(135))
    val = b.getRadius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 35.0

    b.set_facing(math.radians(315))
    val = b.getRadius(math.radians(0))
    print(f"Radius: {val}")
    assert val == 42.7549

