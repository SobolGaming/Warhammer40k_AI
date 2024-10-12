from math import sqrt, atan2

# Determine the distance of a 3D position delta
def getDist(x_delta: float, y_delta: float, z_delta: float = 0) -> float:
    return sqrt(x_delta**2 + y_delta**2 + z_delta**2)

# Determine the angle between to X,Y points
def getAngle(x_delta: float, y_delta: float) -> float:
    return atan2(x_delta, y_delta)