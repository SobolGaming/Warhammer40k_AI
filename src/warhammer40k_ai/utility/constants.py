from math import pi

MM_TO_INCHES = 25.4
VIEWING_ANGLE = pi / 6  # 30 degrees
ENGAGEMENT_RANGE_HORIZONTAL = 1.0  # inches - base-to-base horizontal distance  
ENGAGEMENT_RANGE_VERTICAL = 5.0    # inches - vertical distance
FREELY_CLIMBABLE_RANGE = 2.0  # inches

# Fight phase movement distances
PILE_IN_DISTANCE = 3.0  # inches - standard pile-in distance
CONSOLIDATE_DISTANCE = 3.0  # inches - standard consolidate distance

# Base contact epsilon for discretized positioning
BASE_CONTACT_EPSILON = 0.05  # inches - models within this distance are considered in base contact
TOTAL_ROUNDS = 5