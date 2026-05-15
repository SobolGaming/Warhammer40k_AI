import pygame
from typing import Optional

from warhammer40k_ai.battlefield.map import TerrainFeature, TerrainType


WHITE = (255, 255, 255)
GREY = (50, 50, 50)
RED = (255, 0, 0)


def _draw_alpha_polygon_bounded(
    screen: pygame.Surface,
    points: list[tuple[int, int]],
    fill_rgba: tuple[int, int, int, int],
) -> None:
    if len(points) < 3:
        return
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    width = int(max_x - min_x + 1)
    height = int(max_y - min_y + 1)
    if width <= 0 or height <= 0:
        return
    if not pygame.Rect(min_x, min_y, width, height).colliderect(screen.get_rect()):
        return

    local_points = [(int(x - min_x), int(y - min_y)) for x, y in points]
    temp = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.polygon(temp, fill_rgba, local_points)
    screen.blit(temp, (min_x, min_y))


def draw_battlefield(
    screen: pygame.Surface,
    zoom_level: float,
    offset_x: int,
    offset_y: int,
    *,
    tile_size: int,
    battlefield_width_inches: int,
    battlefield_height_inches: int,
    viewport_width: Optional[int] = None,
    viewport_height: Optional[int] = None,
) -> None:
    """Draw the battlefield grid, background, and border."""
    screen.fill((0, 0, 0))  # Black background outside battlefield
    tile_size_px = int(tile_size * zoom_level)

    visible_width = viewport_width if viewport_width is not None else screen.get_width()
    visible_height = viewport_height if viewport_height is not None else screen.get_height()

    world_w = battlefield_width_inches * tile_size_px
    world_h = battlefield_height_inches * tile_size_px

    bf_left = int(offset_x)
    bf_top = int(offset_y)
    bf_rect = pygame.Rect(bf_left, bf_top, world_w, world_h)

    viewport_rect = pygame.Rect(0, 0, visible_width, visible_height)
    intersect = bf_rect.clip(viewport_rect)
    if intersect.width > 0 and intersect.height > 0:
        pygame.draw.rect(screen, WHITE, intersect)

    start_x_inch = max(0, int((-offset_x) // tile_size_px))
    end_x_inch = min(battlefield_width_inches, int((visible_width - offset_x) // tile_size_px) + 1)
    start_y_inch = max(0, int((-offset_y) // tile_size_px))
    end_y_inch = min(battlefield_height_inches, int((visible_height - offset_y) // tile_size_px) + 1)

    for x_inch in range(start_x_inch, end_x_inch + 1):
        px = int(x_inch * tile_size_px + offset_x)
        if px < bf_left or px > bf_left + world_w:
            continue
        y1 = max(0, bf_top)
        y2 = min(visible_height, bf_top + world_h)
        if y2 > y1:
            pygame.draw.line(screen, GREY, (px, y1), (px, y2))

    for y_inch in range(start_y_inch, end_y_inch + 1):
        py = int(y_inch * tile_size_px + offset_y)
        if py < bf_top or py > bf_top + world_h:
            continue
        x1 = max(0, bf_left)
        x2 = min(visible_width, bf_left + world_w)
        if x2 > x1:
            pygame.draw.line(screen, GREY, (x1, py), (x2, py))

    border_rect = bf_rect.clip(viewport_rect)
    if border_rect.width > 0 and border_rect.height > 0:
        pygame.draw.rect(screen, RED, border_rect, 2)


def draw_terrain_feature(
    screen: pygame.Surface,
    terrain_feature: TerrainFeature,
    zoom_level: float,
    offset_x: int,
    offset_y: int,
    *,
    tile_size: int,
) -> None:
    """Draw a terrain feature footprint, with ruins detailing when available."""
    if terrain_feature.terrain_type == TerrainType.CRATER_AND_RUBBLE:
        color = (128, 0, 0, 180)
    elif terrain_feature.terrain_type == TerrainType.DEBRIS_AND_STATUARY:
        color = (192, 192, 192, 180)
    elif terrain_feature.terrain_type == TerrainType.HILLS_AND_SEALED_BUILDINGS:
        color = (128, 64, 0, 180)
    elif terrain_feature.terrain_type == TerrainType.WOODS:
        color = (0, 128, 0, 180)
    elif terrain_feature.terrain_type == TerrainType.RUINS:
        color = (128, 128, 128, 180)
    elif terrain_feature.terrain_type == TerrainType.BARRICADE_AND_FUEL_PIPES:
        color = (139, 69, 19, 180)
    else:
        color = (255, 255, 255, 180)

    def to_screen(pt):
        return (
            int((pt[0] * tile_size) * zoom_level + offset_x),
            int((pt[1] * tile_size) * zoom_level + offset_y),
        )

    def draw_shapely_polygon(poly, fill_rgba=None, outline_rgb=None, outline_w=1):
        try:
            coords = list(poly.exterior.coords)[:-1]
        except Exception:
            return
        if len(coords) < 3:
            return
        points = [to_screen(v) for v in coords]
        if fill_rgba is not None:
            _draw_alpha_polygon_bounded(screen, points, fill_rgba)
        if outline_rgb is not None and outline_w > 0:
            pygame.draw.polygon(screen, outline_rgb, points, outline_w)

    footprint_coords = list(terrain_feature.footprint.exterior.coords)[:-1]
    screen_vertices = [to_screen(v) for v in footprint_coords]
    if len(screen_vertices) >= 3:
        pygame.draw.polygon(screen, color, screen_vertices)
        pygame.draw.polygon(screen, (0, 0, 0), screen_vertices, 2)

    if terrain_feature.terrain_type == TerrainType.RUINS:
        floors = getattr(terrain_feature, 'floors', []) or []
        for floor in floors:
            poly = floor.get('polygon')
            if poly is None:
                continue
            draw_shapely_polygon(poly, fill_rgba=(80, 120, 200, 90), outline_rgb=(50, 80, 140), outline_w=1)

        walls = getattr(terrain_feature, 'walls', []) or []
        for wall in walls:
            poly = wall.get('polygon')
            if poly is None:
                continue
            draw_shapely_polygon(poly, fill_rgba=(80, 80, 80, 220), outline_rgb=(30, 30, 30), outline_w=1)

        openings = getattr(terrain_feature, 'openings', []) or []
        for opening in openings:
            poly = opening.get('polygon')
            if poly is None:
                continue
            allows_movement = opening.get('allows_movement', False)
            allows_los = opening.get('allows_los', False)
            if allows_movement:
                draw_shapely_polygon(poly, fill_rgba=(50, 200, 120, 180), outline_rgb=(0, 120, 60), outline_w=1)
            elif allows_los:
                draw_shapely_polygon(poly, fill_rgba=(230, 210, 60, 160), outline_rgb=(160, 140, 20), outline_w=1)
            else:
                draw_shapely_polygon(poly, fill_rgba=(200, 200, 200, 140), outline_rgb=(100, 100, 100), outline_w=1)
