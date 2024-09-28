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

def create_ellipse(center: typing.Tuple[float, float], lengths: typing.Tuple[float, float], bearing: float = 0) -> Poly:
    """
    Create a shapely ellipse.
    
    :param center: The center point of the ellipse (x, y)
    :param lengths: The lengths of the ellipse axes (major, minor)
    :param bearing: The rotation of the ellipse in radians
    :return: A shapely Polygon representing the ellipse
    """
    circ = Point(center).buffer(1)
    ell = affinity.scale(circ, lengths[1], lengths[0])
    return affinity.rotate(ell, math.degrees(bearing))

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
        self.facing: float = 0.0
        self.base_type = base_type
        self.radius: typing.Tuple[float, float] = self._normalize_radius(radius)

    def _normalize_radius(self, radius: typing.Union[float, typing.Tuple[float, float]]) -> typing.Tuple[float, float]:
        if isinstance(radius, (float, int)):
            return (float(radius), float(radius))
        elif isinstance(radius, tuple) and len(radius) == 2:
            return (float(radius[0]), float(radius[1]))
        else:
            raise ValueError("Invalid radius format. Expected float or tuple of two floats.")

    # Note: Radius is in "inches"
    # Note: Facing is assumed to be 0 degrees North, 90 degrees East, etc.
    # Note: For ellipses, longer axis is assumed to be first number in tuple()
    def __init__(self, base_type: BaseType, radius: typing.Union[float, typing.Tuple[float, float]]) -> None:
        self.x = 0.0
        self.y = 0.0
        self.facing = 0.0
        self.base_type = base_type
        if isinstance(radius, float) or isinstance(radius, int):
            self.radius = (float(radius), float(radius))
        else:
            self.radius = radius

    def setFacing(self, facing: float):
        self.facing = facing

    # Note: angle is in radians
    def getRadius(self, angle: float = 0.0) -> float:
        if self.base_type == BaseType.CIRCULAR:
            return round(self.radius[0], 4)
        elif self.base_type == BaseType.ELLIPTICAL:
            major_axis = self.radius[0]
            minor_axis = self.radius[1]
            full_angle = (math.pi - self.facing) + angle
            part_1 = math.pow(major_axis, 2) * math.pow(math.sin(full_angle), 2)
            part_2 = math.pow(minor_axis, 2) * math.pow(math.cos(full_angle), 2)
            radius = major_axis * minor_axis / math.sqrt(part_1 + part_2)
            return round(radius, 4)
        elif self.base_type == BaseType.HULL:
            major_axis = self.radius[1]
            minor_axis = self.radius[0]
            full_angle = (math.pi - self.facing) + angle
            corner_angle = math.atan(major_axis/minor_axis)
            radius = 0.0
            if (full_angle >= -corner_angle and full_angle < corner_angle) or \
               (full_angle >= (math.pi - corner_angle) and full_angle <(math.pi + corner_angle)):
                dx = minor_axis
                dy = dx * math.tan(full_angle)
                radius = math.hypot(dx, dy)
            else:
                dx = major_axis / math.tan(full_angle)
                dy = major_axis
                radius = math.hypot(dx, dy)
            assert radius > 0, "bad HULL radius calculation"
            return round(radius, 4)
        else:
            raise Exception(f"Unknown base_type: {self.base_type}")

    # Determine the longest distance to parameter point of base
    def longestDistance(self) -> float:
        if self.base_type in [BaseType.CIRCULAR, BaseType.ELLIPTICAL]:
            return max(self.radius)
        elif self.base_type == BaseType.HULL:
            return math.hypot(self.radius[0], self.radius[1])
        else:
            raise Exception(f"Unknown base_type: {self.base_type}")

    # Get the geometric shape of the base
    def getShape(self) -> any:
        if self.base_type in [BaseType.CIRCULAR, BaseType.ELLIPTICAL]:
            return create_ellipse((self.x, self.y), (self.radius[0], self.radius[1]), self.facing)
        elif self.base_type == BaseType.HULL:
            return create_rectangle((self.x, self.y), (self.radius[0], self.radius[1]), self.facing)
        else:
            raise Exception(f"Unknown BaseType geometry: {self.base_type}")

    # Determine shortest distance between two geometries (bases)
    def shortestDistance(self, other: "Base") -> float:
        shape1 = self.getShape()
        shape2 = other.getShape()
        return round(shape1.distance(shape2), 4)

    # Determine collision with another Base
    def collidesWithBase(self, other: "Base") -> bool:
        dx = other.x - self.x
        dy = other.y - self.y
        # try to see if we can skip complex math
        max_dist = self.longestDistance() + other.longestDistance()
        dist = math.hypot(dx, dy)
        if max_dist < dist:
            logger.debug(f"Quick Non-Collision Decision :: Max D: {max_dist}, D: {dist}")
            return False
        else:
            return self.shortestDistance(other) == 0.0


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

    b.setFacing(math.radians(90))
    val = b.getRadius(math.radians(90))
    print(f"Radius: {val}")
    assert val == 60.0

    b.setFacing(math.radians(315))
    val = b.getRadius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 35.0

    b.setFacing(math.radians(135))
    val = b.getRadius(math.radians(45))
    print(f"Radius: {val}")
    assert val == 35.0

    b.setFacing(math.radians(315))
    val = b.getRadius(math.radians(0))
    print(f"Radius: {val}")
    assert val == 42.7549