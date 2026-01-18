import pygame

from warhammer40k_ai.battlefield.map import Objective, ObjectivePoint
from warhammer40k_ai.roster.player import Player

from ..ui_constants import TILE_SIZE


def draw_deployment_zones(screen: pygame.Surface, deployment_zones: dict, player1: Player, player2: Player, 
                         zoom_level: float, offset_x: int, offset_y: int) -> None:
    """Draw deployment zones with transparency and appropriate colors for each player."""
    for player_name, zone in deployment_zones.items():
        # Determine player color with more vibrant colors during deployment
        if player_name == player1.name:
            color = (0, 255, 0, 160)  # More visible green for player 1
            border_color = (0, 200, 0)
        elif player_name == player2.name:
            color = (255, 0, 0, 160)  # More visible red for player 2
            border_color = (200, 0, 0)
        else:
            color = (128, 128, 128, 160)  # Semi-transparent gray for unknown players
            border_color = (100, 100, 100)
        
        # Check if this is a mission zone (new system) or old system
        if 'mission_zones' in zone:
            # Draw each mission zone polygon
            for mission_zone in zone['mission_zones']:
                # Convert mission zone vertices to screen coordinates
                screen_points = []
                for x, y in mission_zone.vertices:
                    screen_x = int(x * TILE_SIZE * zoom_level + offset_x)
                    screen_y = int(y * TILE_SIZE * zoom_level + offset_y)
                    screen_points.append((screen_x, screen_y))
                
                # Only draw if we have enough points for a polygon
                if len(screen_points) >= 3:
                    # Create a surface for the polygon with alpha
                    # Get bounding box for the surface
                    min_x = min(p[0] for p in screen_points)
                    max_x = max(p[0] for p in screen_points)
                    min_y = min(p[1] for p in screen_points)
                    max_y = max(p[1] for p in screen_points)
                    
                    surface_width = max_x - min_x + 1
                    surface_height = max_y - min_y + 1
                    
                    if surface_width > 0 and surface_height > 0:
                        # Adjust points relative to surface origin
                        relative_points = [(p[0] - min_x, p[1] - min_y) for p in screen_points]
                        
                        # Create transparent surface
                        zone_surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)
                        
                        # Draw filled polygon
                        pygame.draw.polygon(zone_surface, color, relative_points)
                        
                        # Draw cutouts if any exist
                        if hasattr(mission_zone, 'cutouts') and mission_zone.cutouts:
                            for cutout in mission_zone.cutouts:
                                if cutout.cutout_type.value == 'circle':
                                    # Convert cutout center to screen coordinates
                                    cutout_screen_x = int(cutout.center_x * TILE_SIZE * zoom_level + offset_x)
                                    cutout_screen_y = int(cutout.center_y * TILE_SIZE * zoom_level + offset_y)
                                    cutout_radius = int(cutout.parameters * TILE_SIZE * zoom_level)
                                    
                                    # Calculate cutout position relative to surface
                                    cutout_rel_x = cutout_screen_x - min_x
                                    cutout_rel_y = cutout_screen_y - min_y
                                    
                                    # Only draw cutout if it's within the surface bounds
                                    if (cutout_rel_x + cutout_radius >= 0 and cutout_rel_x - cutout_radius < surface_width and
                                        cutout_rel_y + cutout_radius >= 0 and cutout_rel_y - cutout_radius < surface_height):
                                        
                                        # Draw cutout as no man's land (transparent - shows battlefield background)
                                        # Create a "hole" by drawing with full transparency
                                        pygame.draw.circle(zone_surface, (0, 0, 0, 0), 
                                                         (cutout_rel_x, cutout_rel_y), cutout_radius)
                                        # Draw cutout border to show the boundary
                                        pygame.draw.circle(zone_surface, (100, 100, 100), 
                                                         (cutout_rel_x, cutout_rel_y), cutout_radius, 2)
                        
                        # No zone border per request (keep only filled zone and cutout visuals)
                        
                        # Blit to main screen
                        screen.blit(zone_surface, (min_x, min_y))
                        
                        # Add zone label
                        font = pygame.font.Font(None, int(24 * zoom_level))
                        if zone.get('zone_type') == 'defender':
                            label_text = "DEFENDER"
                        elif zone.get('zone_type') == 'attacker':
                            label_text = "ATTACKER"
                        else:
                            label_text = zone.get('name', 'ZONE')
                        
                        text_surface = font.render(label_text, True, border_color)
                        text_rect = text_surface.get_rect()
                        
                        # Center text in the polygon (approximate)
                        center_x = (min_x + max_x) // 2 - text_rect.width // 2
                        center_y = (min_y + max_y) // 2 - text_rect.height // 2
                        screen.blit(text_surface, (center_x, center_y))
        else:
            # Deployment zones must be mission polygon zones; rectangular zones are not supported.
            continue
            
            # Add zone label with better positioning
            font = pygame.font.SysFont('Arial', max(14, int(16 * zoom_level)), bold=True)
            label_text = f"{player_name} Deployment Zone"
            text_surface = font.render(label_text, True, border_color)
            
            # Position label at the center-top of the zone for better visibility
            label_x = screen_x_start + (zone_width - text_surface.get_width()) // 2
            label_y = screen_y_start + 15
            
            # Draw a more prominent background for the text
            text_bg = pygame.Surface((text_surface.get_width() + 12, text_surface.get_height() + 6), pygame.SRCALPHA)
            text_bg.fill((255, 255, 255, 220))  # More opaque white background
            screen.blit(text_bg, (label_x - 6, label_y - 3))
            
            # Draw black outline for better text visibility
            outline_positions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            for dx, dy in outline_positions:
                outline_surface = font.render(label_text, True, (0, 0, 0))
                screen.blit(outline_surface, (label_x + dx, label_y + dy))
            
            # Draw the main text
            screen.blit(text_surface, (label_x, label_y))

def draw_objective(screen: pygame.Surface, objective: Objective, zoom_level: float, offset_x: int, offset_y: int) -> None:
    if isinstance(objective.location, ObjectivePoint):
        # Create a transparent surface for the objective
        objective_radius = int(objective.location.control_radius * TILE_SIZE * zoom_level)
        if objective_radius > 0:
            # Calculate center position
            center_x = int(objective.location.x * TILE_SIZE * zoom_level + offset_x)
            center_y = int(objective.location.y * TILE_SIZE * zoom_level + offset_y)
            
            # Create a surface with per-pixel alpha for transparency
            objective_surface = pygame.Surface((objective_radius * 2, objective_radius * 2), pygame.SRCALPHA)
            
            # Draw objective with 50% transparency (128 alpha instead of 255)
            pygame.draw.circle(objective_surface, (128, 0, 128, 128), (objective_radius, objective_radius), objective_radius)
            
            # Draw border for visibility
            pygame.draw.circle(objective_surface, (128, 0, 128, 255), (objective_radius, objective_radius), objective_radius, 2)
            
            # Blit to main screen
            screen.blit(objective_surface, (center_x - objective_radius, center_y - objective_radius))
