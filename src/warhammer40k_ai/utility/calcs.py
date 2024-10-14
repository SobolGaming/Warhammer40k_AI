from math import sqrt, atan2

MM_TO_INCHES = 25.4
VIEWING_ANGLE = 1.57 / 3 # 30 degrees

# Convert mm (as in base size of models) to inches
def convert_mm_to_inches(value: float) -> float:
    return round(value / MM_TO_INCHES, 4)

# Determine the distance of a 3D position delta
def getDist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between to X,Y points
def getAngle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)