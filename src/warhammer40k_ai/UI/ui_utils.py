"""
Shared UI utility functions for the Warhammer 40k AI interface.
"""

import pygame
from typing import List, Tuple
from ..classes.unit import Unit


def get_unit_color_variation(unit: Unit, all_units: List[Unit]) -> Tuple[int, int, int]:
    """
    Generate a unique color variation for a unit based on its position in the army.
    This helps visually distinguish units on the battlefield and correlate them with roster display.
    """
    if not all_units:
        return (255, 255, 255)  # Default white
    
    try:
        unit_index = all_units.index(unit)
    except ValueError:
        unit_index = 0
    
    # Generate color variations using HSV-like approach
    # Use different hue shifts for each unit while maintaining good visibility
    base_colors = [
        (255, 200, 200),  # Light red
        (200, 255, 200),  # Light green  
        (200, 200, 255),  # Light blue
        (255, 255, 200),  # Light yellow
        (255, 200, 255),  # Light magenta
        (200, 255, 255),  # Light cyan
        (255, 220, 180),  # Light orange
        (220, 180, 255),  # Light purple
        (180, 255, 220),  # Light mint
        (255, 180, 220),  # Light pink
    ]
    
    return base_colors[unit_index % len(base_colors)]


def draw_character_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a character icon (crown/leadership symbol)"""
    # Draw a simple crown shape
    crown_color = (255, 215, 0)  # Gold
    
    # Crown base
    base_rect = pygame.Rect(center_x - size//3, center_y + size//6, size//1.5, size//6)
    pygame.draw.rect(surface, crown_color, base_rect)
    
    # Crown points (triangular spikes)
    points = []
    for i in range(3):
        x_offset = (i - 1) * size//4
        # Base points
        points.extend([
            (center_x + x_offset - size//8, center_y + size//6),
            (center_x + x_offset + size//8, center_y + size//6),
            (center_x + x_offset, center_y - size//4)
        ])
    
    # Draw crown spikes as triangles
    for i in range(0, len(points), 3):
        if i + 2 < len(points):
            triangle_points = [points[i], points[i+1], points[i+2]]
            pygame.draw.polygon(surface, crown_color, triangle_points)


def draw_vehicle_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a vehicle icon (tank-like shape)"""
    vehicle_color = (128, 128, 128)  # Gray
    
    # Main body (rectangle)
    body_rect = pygame.Rect(center_x - size//3, center_y - size//6, size//1.5, size//3)
    pygame.draw.rect(surface, vehicle_color, body_rect)
    
    # Turret (smaller rectangle on top)
    turret_rect = pygame.Rect(center_x - size//6, center_y - size//4, size//3, size//6)
    pygame.draw.rect(surface, vehicle_color, turret_rect)
    
    # Barrel (line extending from turret)
    barrel_start = (center_x + size//6, center_y - size//6)
    barrel_end = (center_x + size//2, center_y - size//6)
    pygame.draw.line(surface, vehicle_color, barrel_start, barrel_end, 3)
    
    # Tracks/wheels (small circles)
    wheel_positions = [
        (center_x - size//4, center_y + size//8),
        (center_x, center_y + size//8),
        (center_x + size//4, center_y + size//8)
    ]
    for pos in wheel_positions:
        pygame.draw.circle(surface, vehicle_color, pos, size//12)


def draw_monster_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a monster icon (creature-like shape)"""
    monster_color = (139, 69, 19)  # Brown
    
    # Body (oval)
    body_rect = pygame.Rect(center_x - size//3, center_y - size//4, size//1.5, size//2)
    pygame.draw.ellipse(surface, monster_color, body_rect)
    
    # Head (smaller circle)
    head_center = (center_x, center_y - size//3)
    pygame.draw.circle(surface, monster_color, head_center, size//6)
    
    # Limbs (lines extending from body)
    limb_positions = [
        ((center_x - size//4, center_y), (center_x - size//2, center_y + size//4)),  # Left arm
        ((center_x + size//4, center_y), (center_x + size//2, center_y + size//4)),  # Right arm
        ((center_x - size//6, center_y + size//6), (center_x - size//4, center_y + size//2)),  # Left leg
        ((center_x + size//6, center_y + size//6), (center_x + size//4, center_y + size//2))   # Right leg
    ]
    
    for start, end in limb_positions:
        pygame.draw.line(surface, monster_color, start, end, 3)


def draw_battleline_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a battleline icon (shield symbol)"""
    shield_color = (70, 130, 180)  # Steel blue
    
    # Shield shape (rounded rectangle with pointed bottom)
    shield_points = [
        (center_x - size//3, center_y - size//3),  # Top left
        (center_x + size//3, center_y - size//3),  # Top right
        (center_x + size//3, center_y + size//6),  # Bottom right
        (center_x, center_y + size//2),           # Bottom point
        (center_x - size//3, center_y + size//6), # Bottom left
    ]
    pygame.draw.polygon(surface, shield_color, shield_points)
    
    # Cross or emblem on shield
    cross_color = (255, 255, 255)  # White
    # Vertical line
    pygame.draw.line(surface, cross_color, 
                    (center_x, center_y - size//6), 
                    (center_x, center_y + size//6), 3)
    # Horizontal line
    pygame.draw.line(surface, cross_color, 
                    (center_x - size//6, center_y), 
                    (center_x + size//6, center_y), 3)


def draw_aircraft_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw an aircraft icon (plane shape)"""
    aircraft_color = (105, 105, 105)  # Dim gray
    
    # Main fuselage (elongated oval)
    fuselage_rect = pygame.Rect(center_x - size//2, center_y - size//8, size, size//4)
    pygame.draw.ellipse(surface, aircraft_color, fuselage_rect)
    
    # Wings (triangular shapes)
    wing_points = [
        # Left wing
        [(center_x - size//4, center_y), (center_x - size//2, center_y - size//3), (center_x, center_y)],
        # Right wing  
        [(center_x + size//4, center_y), (center_x + size//2, center_y - size//3), (center_x, center_y)]
    ]
    
    for wing in wing_points:
        pygame.draw.polygon(surface, aircraft_color, wing)
    
    # Tail (small triangle at back)
    tail_points = [
        (center_x + size//3, center_y),
        (center_x + size//2, center_y - size//6),
        (center_x + size//2, center_y + size//6)
    ]
    pygame.draw.polygon(surface, aircraft_color, tail_points)


def draw_beast_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a beast icon (animal-like shape)"""
    beast_color = (160, 82, 45)  # Saddle brown
    
    # Body (horizontal oval)
    body_rect = pygame.Rect(center_x - size//2, center_y - size//6, size, size//3)
    pygame.draw.ellipse(surface, beast_color, body_rect)
    
    # Head (circle at front)
    head_center = (center_x - size//3, center_y)
    pygame.draw.circle(surface, beast_color, head_center, size//6)
    
    # Legs (short lines)
    leg_positions = [
        ((center_x - size//4, center_y + size//6), (center_x - size//4, center_y + size//3)),
        ((center_x - size//8, center_y + size//6), (center_x - size//8, center_y + size//3)),
        ((center_x + size//8, center_y + size//6), (center_x + size//8, center_y + size//3)),
        ((center_x + size//4, center_y + size//6), (center_x + size//4, center_y + size//3))
    ]
    
    for start, end in leg_positions:
        pygame.draw.line(surface, beast_color, start, end, 2)
    
    # Tail (curved line)
    tail_start = (center_x + size//2, center_y)
    tail_end = (center_x + size//2 + size//4, center_y - size//4)
    pygame.draw.line(surface, beast_color, tail_start, tail_end, 2)


def draw_psyker_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a mystical eye icon for psykers"""
    from math import cos, sin
    
    eye_color = (138, 43, 226)  # Blue violet
    pupil_color = (75, 0, 130)  # Indigo
    outline_color = (0, 0, 0)
    
    # Draw outer eye shape (ellipse)
    eye_rect = pygame.Rect(center_x - size//2, center_y - size//3, size, size//1.5)
    pygame.draw.ellipse(surface, eye_color, eye_rect)
    pygame.draw.ellipse(surface, outline_color, eye_rect, 2)
    
    # Draw pupil (circle)
    pupil_radius = size//4
    pygame.draw.circle(surface, pupil_color, (center_x, center_y), pupil_radius)
    pygame.draw.circle(surface, outline_color, (center_x, center_y), pupil_radius, 1)
    
    # Draw mystical lines radiating from eye
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        angle_rad = angle * 3.14159 / 180
        start_x = center_x + (size//2 + 2) * cos(angle_rad)
        start_y = center_y + (size//2 + 2) * sin(angle_rad)
        end_x = center_x + (size//2 + 6) * cos(angle_rad)
        end_y = center_y + (size//2 + 6) * sin(angle_rad)
        pygame.draw.line(surface, eye_color, (start_x, start_y), (end_x, end_y), 1)


def draw_generic_icon(surface: pygame.Surface, center_x: int, center_y: int, size: int) -> None:
    """Draw a generic unit icon (simple soldier silhouette)"""
    generic_color = (169, 169, 169)  # Dark gray
    
    # Head (circle)
    head_center = (center_x, center_y - size//3)
    pygame.draw.circle(surface, generic_color, head_center, size//8)
    
    # Body (rectangle)
    body_rect = pygame.Rect(center_x - size//8, center_y - size//4, size//4, size//2)
    pygame.draw.rect(surface, generic_color, body_rect)
    
    # Arms (lines)
    arm_positions = [
        ((center_x - size//8, center_y - size//6), (center_x - size//4, center_y)),  # Left arm
        ((center_x + size//8, center_y - size//6), (center_x + size//4, center_y))   # Right arm
    ]
    
    for start, end in arm_positions:
        pygame.draw.line(surface, generic_color, start, end, 2)
    
    # Legs (lines)
    leg_positions = [
        ((center_x - size//16, center_y + size//4), (center_x - size//8, center_y + size//2)),  # Left leg
        ((center_x + size//16, center_y + size//4), (center_x + size//8, center_y + size//2))   # Right leg
    ]
    
    for start, end in leg_positions:
        pygame.draw.line(surface, generic_color, start, end, 2) 