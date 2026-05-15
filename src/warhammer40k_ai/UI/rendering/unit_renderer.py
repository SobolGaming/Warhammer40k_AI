import math
from typing import List, Optional, Tuple

import pygame

from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType

from ..ui_constants import BLUE, GREEN, RED, ICON_MIN_SIZE, ICON_SCALE_FACTOR, TILE_SIZE
from ..ui_utils import (
    draw_aircraft_icon,
    draw_battleline_icon,
    draw_beast_icon,
    draw_character_icon,
    draw_generic_icon,
    draw_monster_icon,
    draw_psyker_icon,
    draw_vehicle_icon,
    get_unit_color_variation,
)


_FONT_CACHE: dict[int, pygame.font.Font] = {}
_BACKGROUND_SURFACE_CACHE: dict[tuple[int, tuple[int, int, int, int]], pygame.Surface] = {}
_ICON_SURFACE_CACHE: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
_ROTATED_ICON_CACHE: dict[tuple[str, int, tuple[int, int, int], int], pygame.Surface] = {}
_MAX_SURFACE_CACHE_SIZE = 512


def _bounded_cache_set(cache: dict, key: object, value: pygame.Surface) -> pygame.Surface:
    if len(cache) >= _MAX_SURFACE_CACHE_SIZE:
        cache.clear()
    cache[key] = value
    return value


def _font_for_size(font_size: int) -> pygame.font.Font:
    size = max(1, int(font_size))
    font = _FONT_CACHE.get(size)
    if font is None:
        font = pygame.font.Font(None, size)
        _FONT_CACHE[size] = font
    return font


def _unit_icon_kind(unit: Unit) -> str:
    if unit.is_vehicle:
        return "vehicle"
    if unit.is_monster:
        return "monster"
    if unit.is_aircraft:
        return "aircraft"
    if unit.is_beast:
        return "beast"
    if unit.is_psyker:
        return "psyker"
    if unit.is_battleline:
        return "battleline"
    if unit.is_character:
        return "character"
    return "generic"


def _draw_icon_by_kind(surface: pygame.Surface, icon_kind: str, center: int, size: int) -> None:
    if icon_kind == "vehicle":
        draw_vehicle_icon(surface, center, center, size)
    elif icon_kind == "monster":
        draw_monster_icon(surface, center, center, size)
    elif icon_kind == "aircraft":
        draw_aircraft_icon(surface, center, center, size)
    elif icon_kind == "beast":
        draw_beast_icon(surface, center, center, size)
    elif icon_kind == "psyker":
        draw_psyker_icon(surface, center, center, size)
    elif icon_kind == "battleline":
        draw_battleline_icon(surface, center, center, size)
    elif icon_kind == "character":
        draw_character_icon(surface, center, center, size)
    else:
        draw_generic_icon(surface, center, center, size)


def _cached_background_surface(radius: int, color: tuple[int, int, int, int]) -> pygame.Surface:
    key = (int(radius), color)
    cached = _BACKGROUND_SURFACE_CACHE.get(key)
    if cached is not None:
        return cached
    surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(surface, color, (radius, radius), radius)
    return _bounded_cache_set(_BACKGROUND_SURFACE_CACHE, key, surface)


def _cached_icon_surface(icon_kind: str, size: int, tint_color: Tuple[int, int, int]) -> pygame.Surface:
    key = (str(icon_kind), int(size), tuple(tint_color))
    cached = _ICON_SURFACE_CACHE.get(key)
    if cached is not None:
        return cached

    surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
    icon_center = size * 3 // 2
    _draw_icon_by_kind(surface, icon_kind, icon_center, size)
    if tint_color != (255, 255, 255):
        tint_surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
        tint_surface.fill((*tint_color, 120))
        surface.blit(tint_surface, (0, 0), special_flags=pygame.BLEND_MULT)
    return _bounded_cache_set(_ICON_SURFACE_CACHE, key, surface)


def _cached_rotated_icon_surface(
    icon_kind: str,
    size: int,
    tint_color: Tuple[int, int, int],
    angle: float,
) -> pygame.Surface:
    angle_bucket = int(round(math.degrees(float(angle))))
    key = (str(icon_kind), int(size), tuple(tint_color), angle_bucket)
    cached = _ROTATED_ICON_CACHE.get(key)
    if cached is not None:
        return cached
    icon_surface = _cached_icon_surface(icon_kind, size, tint_color)
    rotated_surface = pygame.transform.rotate(icon_surface, -angle_bucket)
    return _bounded_cache_set(_ROTATED_ICON_CACHE, key, rotated_surface)


def _model_visible_on_screen(screen: pygame.Surface, screen_x: int, screen_y: int, base: Base, zoom_level: float) -> bool:
    get_radius = getattr(base, "get_longest_radius", None)
    if callable(get_radius):
        base_radius = float(get_radius())
    else:
        base_radius = float(base.get_radius())
    margin = max(ICON_MIN_SIZE, int(base_radius * TILE_SIZE * zoom_level * 2.0)) + 24
    return (
        screen_x >= -margin
        and screen_y >= -margin
        and screen_x <= screen.get_width() + margin
        and screen_y <= screen.get_height() + margin
    )


def draw_units(
    screen: pygame.Surface,
    unit: Unit,
    zoom_level: float,
    offset_x: int,
    offset_y: int,
    mouse_pos: Tuple[int, int],
    player1: Player,
    player2: Player,
    highlighted_model_index: Optional[int] = None,
    model_indices_to_draw: Optional[set[int]] = None,
) -> None:
    # Determine the color based on which player the unit belongs to (only if armies are loaded)
    color = BLUE  # Default color
    if (player1.get_army() and player1.get_army().units and unit in player1.get_army().units):
        color = GREEN
    elif (player2.get_army() and player2.get_army().units and unit in player2.get_army().units):
        color = RED

    # Get all units for color variation calculation (only if armies are loaded)
    all_units = []
    if player1.get_army() and player1.get_army().units:
        all_units.extend(player1.get_army().units)
    if player2.get_army() and player2.get_army().units:
        all_units.extend(player2.get_army().units)

    # For "deploy" previews, the dialog passes a unit-like object where indices must match the dialog's models list.
    if model_indices_to_draw is not None:
        models = unit.models
    else:
        try:
            models = unit.get_models_for_rendering()
        except Exception:
            models = unit.models

    for model_index, model in enumerate(models):
        if model_indices_to_draw is not None and model_index not in model_indices_to_draw:
            continue
        x, y = model.get_location()[:2]
        screen_x = int((x * TILE_SIZE) * zoom_level + offset_x)
        screen_y = int((y * TILE_SIZE) * zoom_level + offset_y)
        base = model.model_base
        if not _model_visible_on_screen(screen, screen_x, screen_y, base, zoom_level):
            continue

        # Check if this model should be highlighted
        is_highlighted = (highlighted_model_index is not None and
                         highlighted_model_index == model_index)

        draw_enhanced_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)

        # Draw facing direction with enhanced styling
        draw_facing_direction(screen, base, screen_x, screen_y, zoom_level)

        # Draw large prominent icon that overlays the facing arrow
        draw_prominent_unit_icon(screen, screen_x, screen_y, base, zoom_level, unit, model, model_index, all_units, is_highlighted)

            # Unit bounding box removed - model-based hover detection is more accurate

def draw_prominent_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, base: Base, zoom_level: float, unit: Unit, model: Model, model_index: int, all_units: List[Unit], is_highlighted: bool = False) -> None:
    """Draw a large, prominent icon that overlays the facing direction"""
    # Calculate icon size - larger and with minimum size
    base_radius = int(base.get_radius() * TILE_SIZE * zoom_level)
    icon_size = max(ICON_MIN_SIZE, int(base_radius * ICON_SCALE_FACTOR))

    # Get unit-specific color variation
    icon_tint = get_unit_color_variation(unit, all_units)

    # Draw semi-transparent background circle for better visibility
    bg_radius = icon_size // 2 + 4
    bg_color = (255, 255, 0, 150) if is_highlighted else (0, 0, 0, 100)
    bg_surface = _cached_background_surface(bg_radius, bg_color)
    screen.blit(bg_surface, (center_x - bg_radius, center_y - bg_radius))

    # Draw the unit type icon with color tinting and rotation
    draw_rotated_tinted_unit_icon(screen, center_x, center_y, icon_size, unit, icon_tint, base.facing)

    # For multi-model units, draw individual model identifier
    try:
        models = unit.get_models_for_rendering()
    except Exception:
        models = getattr(unit, "models", []) or []
    if len(models) > 1:
        draw_model_identifier(screen, center_x, center_y, icon_size, model_index, unit, is_highlighted)

    # Draw wound indicator if model is damaged
    if not model.is_max_health:
        draw_prominent_wound_indicator(screen, center_x, center_y, icon_size, model)

def draw_rotated_tinted_unit_icon(screen: pygame.Surface, center_x: int, center_y: int, size: int, unit: Unit, tint_color: Tuple[int, int, int], angle: float) -> None:
    """Draw unit icon with color tinting and rotation based on facing direction"""
    icon_kind = _unit_icon_kind(unit)
    rotated_surface = _cached_rotated_icon_surface(icon_kind, size, tint_color, angle)

    # Calculate the position to blit the rotated surface (centered)
    blit_x = center_x - rotated_surface.get_width() // 2
    blit_y = center_y - rotated_surface.get_height() // 2

    # Blit the rotated icon to the screen
    screen.blit(rotated_surface, (blit_x, blit_y))

def draw_model_identifier(screen: pygame.Surface, center_x: int, center_y: int, icon_size: int, model_index: int, unit: Unit, is_highlighted: bool = False) -> None:
    """Draw individual model identifier for multi-model units"""
    # Position the identifier at the top-right of the icon with more offset
    identifier_size = max(12, icon_size // 3)
    identifier_x = center_x + icon_size // 2 - identifier_size // 4  # More to the right
    identifier_y = center_y - icon_size // 2 + identifier_size // 4  # More up

    # Draw background circle with highlighting
    bg_color = (255, 255, 100) if is_highlighted else (255, 255, 255)
    border_color = (255, 255, 0) if is_highlighted else (0, 0, 0)
    border_width = 3 if is_highlighted else 2

    pygame.draw.circle(screen, bg_color, (identifier_x, identifier_y), identifier_size // 2 + 2)
    pygame.draw.circle(screen, border_color, (identifier_x, identifier_y), identifier_size // 2 + 2, border_width)

    # Draw model number (1-indexed for user friendliness)
    font_size = max(10, identifier_size)
    font = _font_for_size(font_size)
    model_number = str(model_index + 1)
    text_color = (0, 0, 0) if not is_highlighted else (100, 100, 0)
    text_surface = font.render(model_number, True, text_color)
    text_rect = text_surface.get_rect(center=(identifier_x, identifier_y))
    screen.blit(text_surface, text_rect)

def draw_prominent_wound_indicator(screen: pygame.Surface, center_x: int, center_y: int, icon_size: int, model: Model) -> None:
    """Draw a prominent wound indicator for damaged models"""
    if model.is_max_health:
        return

    # Position at bottom of icon
    indicator_y = center_y + icon_size // 2 + 8

    # Larger background for better visibility
    bg_width = max(30, icon_size // 2)
    bg_height = 14
    bg_rect = pygame.Rect(center_x - bg_width // 2, indicator_y - bg_height // 2, bg_width, bg_height)

    # Background with strong contrast
    pygame.draw.rect(screen, (0, 0, 0), bg_rect, border_radius=4)
    pygame.draw.rect(screen, (255, 255, 255), bg_rect, 2, border_radius=4)

    # Wound text with larger font
    font_size = max(12, int(14))
    font = _font_for_size(font_size)
    wound_text = f"{model.wounds}/{model._base_wounds}"

    # Color based on health level
    health_percent = model.health_percent
    if health_percent < 25:
        text_color = (255, 100, 100)  # Light red
    elif health_percent < 50:
        text_color = (255, 200, 100)  # Light orange
    elif health_percent < 75:
        text_color = (255, 255, 100)  # Light yellow
    else:
        text_color = (100, 255, 100)  # Light green

    text_surface = font.render(wound_text, True, text_color)
    text_rect = text_surface.get_rect(center=(center_x, indicator_y))
    screen.blit(text_surface, text_rect)

def draw_unit_identification(screen: pygame.Surface, screen_x: int, screen_y: int, radius: int, unit: Unit, model: Model, zoom_level: float) -> None:
    """Draw unit identification elements for circular bases - now simplified since we have prominent icons"""
    # This function is now mainly for the health indicator ring
    draw_health_indicator(screen, screen_x, screen_y, radius, model)

def draw_unit_identification_on_surface(surface: pygame.Surface, center_x: int, center_y: int, radius: int, unit: Unit, model: Model, zoom_level: float) -> None:
    """Draw unit identification elements on a surface - now simplified since we have prominent icons"""
    # This function is now mainly for the health indicator ring
    # Note: Health indicator is drawn separately for surface-based rendering
    pass

def draw_enhanced_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced base drawing with unit identification features"""
    if base.base_type == BaseType.CIRCULAR:
        draw_enhanced_circular_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)
    elif base.base_type == BaseType.ELLIPTICAL:
        draw_enhanced_elliptical_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)
    elif base.base_type == BaseType.HULL:
        draw_enhanced_hull_base(screen, base, screen_x, screen_y, zoom_level, color, unit, model, is_highlighted)

def draw_enhanced_circular_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced circular base with unit identification"""
    radius = int(base.get_radius() * TILE_SIZE * zoom_level)

    # Draw highlighting ring if highlighted
    if is_highlighted:
        highlight_radius = radius + 4
        pygame.draw.circle(screen, (255, 255, 0), (screen_x, screen_y), highlight_radius, 3)

    # Draw outer ring with gradient effect
    pygame.draw.circle(screen, color, (screen_x, screen_y), radius)

    # Draw inner area with unit-specific styling - scale properly with zoom
    inner_radius = max(1, int(radius * 0.85))
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.circle(screen, inner_color, (screen_x, screen_y), inner_radius)

    # Add unit identification elements
    draw_unit_identification(screen, screen_x, screen_y, radius, unit, model, zoom_level)

def draw_enhanced_elliptical_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced elliptical base with unit identification"""
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)

    # Ensure minimum size for visibility
    width = max(4, width)
    height = max(4, height)

    # Draw highlighting ellipse if highlighted
    if is_highlighted:
        highlight_width = width + 8
        highlight_height = height + 8
        highlight_rect = pygame.Rect(screen_x - highlight_width//2, screen_y - highlight_height//2, highlight_width, highlight_height)
        pygame.draw.ellipse(screen, (255, 255, 0), highlight_rect, 3)

    # Create a surface for the ellipse
    ellipse_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    ellipse_surface.fill((0, 0, 0, 0))  # Transparent background

    # Draw the outer ellipse
    pygame.draw.ellipse(ellipse_surface, color, (0, 0, width, height))

    # Draw the inner ellipse with unit-specific styling - scale properly with zoom
    inner_width, inner_height = max(1, int(width * 0.85)), max(1, int(height * 0.85))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.ellipse(ellipse_surface, inner_color, inner_rect)

    # Add unit identification on the surface before rotation
    draw_unit_identification_on_surface(ellipse_surface, width//2, height//2, min(width, height)//2, unit, model, zoom_level)

    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(ellipse_surface, -angle_degrees)

    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2,
                screen_y - rotated_surface.get_height() // 2)

    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def draw_enhanced_hull_base(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float, color: Tuple[int, int, int], unit: Unit, model: Model, is_highlighted: bool = False) -> None:
    """Enhanced hull base with unit identification"""
    width = int(base.radius[0] * 2 * TILE_SIZE * zoom_level)
    height = int(base.radius[1] * 2 * TILE_SIZE * zoom_level)

    # Ensure minimum size for visibility
    width = max(4, width)
    height = max(4, height)

    # Draw highlighting rectangle if highlighted
    if is_highlighted:
        highlight_width = width + 8
        highlight_height = height + 8
        highlight_rect = pygame.Rect(screen_x - highlight_width//2, screen_y - highlight_height//2, highlight_width, highlight_height)
        pygame.draw.rect(screen, (255, 255, 0), highlight_rect, 3)

    # Create a surface for the hull
    hull_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    hull_surface.fill((0, 0, 0, 0))  # Transparent background

    # Draw the outer hull
    pygame.draw.rect(hull_surface, color, (0, 0, width, height))

    # Draw the inner hull with unit-specific styling - scale properly with zoom
    inner_width, inner_height = max(1, int(width * 0.85)), max(1, int(height * 0.85))
    inner_rect = pygame.Rect((width - inner_width) // 2, (height - inner_height) // 2, inner_width, inner_height)
    inner_color = get_unit_inner_color(unit, model)
    pygame.draw.rect(hull_surface, inner_color, inner_rect)

    # Add unit identification on the surface before rotation
    draw_unit_identification_on_surface(hull_surface, width//2, height//2, min(width, height)//2, unit, model, zoom_level)

    # Rotate the surface
    angle_degrees = math.degrees(base.facing)
    rotated_surface = pygame.transform.rotate(hull_surface, -angle_degrees)

    # Calculate the position to blit the rotated surface
    blit_pos = (screen_x - rotated_surface.get_width() // 2,
                screen_y - rotated_surface.get_height() // 2)

    # Blit the rotated surface onto the screen
    screen.blit(rotated_surface, blit_pos)

def get_unit_inner_color(unit: Unit, model: Model) -> Tuple[int, int, int]:
    """Get the inner color based on unit type and health"""
    # Base inner color based on unit type
    if unit.is_character:
        base_color = (255, 215, 0)  # Gold for characters
    elif unit.is_vehicle:
        base_color = (169, 169, 169)  # Silver for vehicles
    elif unit.is_monster:
        base_color = (139, 69, 19)  # Brown for monsters
    elif unit.is_psyker:
        base_color = (138, 43, 226)  # Blue violet for psykers
    elif unit.is_battleline:
        base_color = (255, 255, 255)  # White for battleline
    else:
        base_color = (220, 220, 220)  # Light gray for others

    # Modify color based on health
    health_percent = model.health_percent
    if health_percent < 25:
        # Heavily damaged - add red tint
        return (min(255, base_color[0] + 50), max(0, base_color[1] - 50), max(0, base_color[2] - 50))
    elif health_percent < 50:
        # Moderately damaged - add yellow tint
        return (min(255, base_color[0] + 30), min(255, base_color[1] + 30), max(0, base_color[2] - 30))
    else:
        return base_color

def draw_health_indicator(screen: pygame.Surface, screen_x: int, screen_y: int, radius: int, model: Model) -> None:
    """Draw a health indicator ring around the base"""
    if radius < 8:  # Too small for health indicator
        return

    health_percent = model.health_percent
    if health_percent >= 100:
        return  # No indicator needed for full health

    # Calculate the arc angle based on health percentage
    arc_angle = int(360 * (health_percent / 100))

    # Choose color based on health level
    if health_percent < 25:
        health_color = (255, 0, 0)  # Red
    elif health_percent < 50:
        health_color = (255, 165, 0)  # Orange
    elif health_percent < 75:
        health_color = (255, 255, 0)  # Yellow
    else:
        health_color = (0, 255, 0)  # Green

    # Draw health arc (simplified approach using lines)
    health_radius = radius + 2
    for angle in range(0, arc_angle, 5):
        angle_rad = math.radians(angle - 90)  # Start from top
        x1 = screen_x + int(health_radius * math.cos(angle_rad))
        y1 = screen_y + int(health_radius * math.sin(angle_rad))
        x2 = screen_x + int((health_radius + 3) * math.cos(angle_rad))
        y2 = screen_y + int((health_radius + 3) * math.sin(angle_rad))
        pygame.draw.line(screen, health_color, (x1, y1), (x2, y2), 2)

def draw_facing_direction(screen: pygame.Surface, base: Base, screen_x: int, screen_y: int, zoom_level: float) -> None:
    """Draw enhanced facing direction indicator"""
    # Calculate the facing line end point
    if base.base_type == BaseType.CIRCULAR:
        radius = int(base.get_radius() * TILE_SIZE * zoom_level)
        line_length = radius
    elif base.base_type in [BaseType.ELLIPTICAL, BaseType.HULL]:
        radius = int(base.get_longest_radius() * TILE_SIZE * zoom_level)
        line_length = radius
    else:
        return  # Skip if base type is unknown

    end_x = screen_x + int(line_length * math.cos(base.facing))
    end_y = screen_y + int(line_length * math.sin(base.facing))

    # Draw the main facing line with enhanced styling
    pygame.draw.line(screen, (0, 0, 0), (screen_x, screen_y), (end_x, end_y), 3)

    # Draw arrowhead
    if line_length > 10:  # Only draw arrowhead if line is long enough
        arrow_length = min(8, line_length // 3)
        arrow_angle = 0.5  # radians

        # Calculate arrowhead points
        left_x = end_x - int(arrow_length * math.cos(base.facing - arrow_angle))
        left_y = end_y - int(arrow_length * math.sin(base.facing - arrow_angle))
        right_x = end_x - int(arrow_length * math.cos(base.facing + arrow_angle))
        right_y = end_y - int(arrow_length * math.sin(base.facing + arrow_angle))

        # Draw arrowhead
        pygame.draw.polygon(screen, (0, 0, 0), [(end_x, end_y), (left_x, left_y), (right_x, right_y)])

# draw_unit_bounding_box function removed - redundant with model-based hover detection
