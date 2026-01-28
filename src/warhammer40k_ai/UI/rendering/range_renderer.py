import pygame

from ..ui_constants import TILE_SIZE


def draw_individual_model_movement_range(screen: pygame.Surface, model, movement_type: str, max_distance: float, zoom_level: float, offset_x: int, offset_y: int, game_map=None) -> None:
    """Draw a visual indicator showing the movement range for an individual model"""
    if not model or (not model.is_alive and not bool(getattr(model, "_careen_pending_move", False))) or max_distance <= 0:
        return

    # Get model position
    model_location = model.get_location()
    current_position = (model_location[0], model_location[1], model_location[2])

    # Convert model position to screen coordinates (respect zoom and UI scaling)
    center_x = int(current_position[0] * TILE_SIZE * zoom_level + offset_x)
    center_y = int(current_position[1] * TILE_SIZE * zoom_level + offset_y)

    # Calculate radius in screen pixels (respect scaling)
    radius = int(max_distance * TILE_SIZE * zoom_level)

    # Choose color based on movement type
    if movement_type == 'scout':
        color = (0, 255, 255, 64)  # Cyan for scout moves
        border_color = (0, 200, 200)
    elif movement_type == 'move':
        color = (0, 255, 0, 64)  # Green for normal move
        border_color = (0, 200, 0)
    elif movement_type == 'advance':
        color = (255, 255, 0, 64)  # Yellow for advance
        border_color = (200, 200, 0)
    elif movement_type == 'fall_back':
        color = (255, 165, 0, 64)  # Orange for fall back
        border_color = (200, 130, 0)
    elif movement_type == 'careen':
        color = (255, 80, 0, 64)  # Orange-red for Careen
        border_color = (220, 60, 0)
    elif movement_type == 'pile_in':
        color = (255, 0, 255, 64)  # Magenta for pile-in
        border_color = (200, 0, 200)
    elif movement_type == 'consolidate':
        color = (255, 128, 255, 64)  # Light magenta for consolidate
        border_color = (200, 100, 200)
    else:
        color = (128, 128, 128, 64)  # Gray for other types
        border_color = (100, 100, 100)

    # Special handling for pile-in movement
    if movement_type == 'pile_in' and game_map:
        draw_pile_in_range(screen, model, current_position, max_distance, zoom_level, offset_x, offset_y, game_map)
    else:
        # Standard circular range for other movement types
        if radius > 0:
            # Create a surface with per-pixel alpha for the range circle
            range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surface, color, (radius, radius), radius)

            # Blit the transparent range circle onto the battlefield
            screen.blit(range_surface, (center_x - radius, center_y - radius))

            # Draw the border circle
            pygame.draw.circle(screen, border_color, (center_x, center_y), radius, 2)


def draw_pile_in_range(screen: pygame.Surface, model, current_position: tuple, max_distance: float, 
                      zoom_level: float, offset_x: int, offset_y: int, game_map) -> None:
    """
    Draw pile-in movement range visualization showing intersection of:
    1. 3" movement circle
    2. Area closer to closest enemy model
    """
    # Find the closest enemy model
    closest_enemy = None
    closest_distance = float('inf')
    
    for unit in game_map.units:
        if unit.faction == model.parent_unit.faction or not unit.is_alive() or not unit.deployed:
            continue
        for enemy_model in unit.models:
            if not enemy_model.is_alive:
                continue
                
            from ...utility.aura_utils import distance_between_models_bases_3d
            distance = float(distance_between_models_bases_3d(model, enemy_model))
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy = enemy_model
    
    if not closest_enemy:
        # No enemies found - draw standard circle
        radius = int(max_distance * TILE_SIZE * zoom_level)
        center_x = int(current_position[0] * TILE_SIZE * zoom_level + offset_x)
        center_y = int(current_position[1] * TILE_SIZE * zoom_level + offset_y)
        
        if radius > 0:
            range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surface, (255, 0, 255, 64), (radius, radius), radius)
            screen.blit(range_surface, (center_x - radius, center_y - radius))
            pygame.draw.circle(screen, (200, 0, 200), (center_x, center_y), radius, 2)
        return
    
    # Get enemy position
    enemy_location = closest_enemy.get_location()
    enemy_position = (enemy_location[0], enemy_location[1])
    
    print(f"DEBUG: Drawing pile-in range for {model.name} vs closest enemy {closest_enemy.name} at {closest_distance:.2f}\"")
    
    # Draw the intersection of movement circle and "closer to enemy" area
    draw_pile_in_intersection(screen, current_position[:2], enemy_position, closest_distance, 
                             max_distance, zoom_level, offset_x, offset_y)
    
    # Draw helpful indicators
    draw_pile_in_indicators(screen, current_position[:2], enemy_position, closest_distance,
                           max_distance, zoom_level, offset_x, offset_y, closest_enemy.name)


def draw_pile_in_intersection(screen: pygame.Surface, model_pos: tuple, enemy_pos: tuple, 
                             current_distance: float, pile_in_distance: float,
                             zoom_level: float, offset_x: int, offset_y: int) -> None:
    """
    Draw the intersection area using polygon approximation for the complex shape
    """
    import math
    
    # Convert positions to screen coordinates
    model_screen_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
    model_screen_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
    enemy_screen_x = int(enemy_pos[0] * TILE_SIZE * zoom_level + offset_x)
    enemy_screen_y = int(enemy_pos[1] * TILE_SIZE * zoom_level + offset_y)
    
    # Calculate pile-in circle radius in screen pixels
    pile_in_radius = int(pile_in_distance * TILE_SIZE * zoom_level)
    
    # Generate points for the valid pile-in area
    valid_points = []
    
    # Sample points around the pile-in circle
    num_samples = 180  # More samples for smoother curve
    for i in range(num_samples):
        angle = 2 * math.pi * i / num_samples
        
        # Point on the pile-in circle
        test_x = model_screen_x + pile_in_radius * math.cos(angle)
        test_y = model_screen_y + pile_in_radius * math.sin(angle)
        
        # Convert back to game coordinates to test distance
        test_game_x = (test_x - offset_x) / (TILE_SIZE * zoom_level)
        test_game_y = (test_y - offset_y) / (TILE_SIZE * zoom_level)
        
        # Calculate distance from this test point to enemy
        test_distance = math.sqrt((test_game_x - enemy_pos[0])**2 + (test_game_y - enemy_pos[1])**2)
        
        # Only include points that are closer to the enemy than current distance
        if test_distance < current_distance:
            valid_points.append((test_x, test_y))
    
    # Draw the valid area if we have enough points
    if len(valid_points) >= 3:
        # Create surface for the filled area
        pile_in_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        
        # Draw filled polygon for valid pile-in area
        pygame.draw.polygon(pile_in_surface, (255, 0, 255, 80), valid_points)  # Bright magenta
        screen.blit(pile_in_surface, (0, 0))
        
        # Draw border outline
        if len(valid_points) > 1:
            pygame.draw.polygon(screen, (255, 0, 255), valid_points, 3)  # Thick magenta border
    
    # Always draw the full pile-in circle as reference (dimmed)
    pygame.draw.circle(screen, (200, 0, 200, 30), (model_screen_x, model_screen_y), pile_in_radius, 2)


def draw_pile_in_indicators(screen: pygame.Surface, model_pos: tuple, enemy_pos: tuple,
                           current_distance: float, pile_in_distance: float,
                           zoom_level: float, offset_x: int, offset_y: int, enemy_name: str) -> None:
    """
    Draw helpful indicators for pile-in movement
    """
    # Convert positions to screen coordinates
    model_screen_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
    model_screen_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
    enemy_screen_x = int(enemy_pos[0] * TILE_SIZE * zoom_level + offset_x)
    enemy_screen_y = int(enemy_pos[1] * TILE_SIZE * zoom_level + offset_y)
    
    # Draw line to closest enemy
    pygame.draw.line(screen, (255, 255, 0), (model_screen_x, model_screen_y), 
                    (enemy_screen_x, enemy_screen_y), 2)  # Yellow line
    
    # Draw enemy highlight circle
    enemy_highlight_radius = int(0.5 * TILE_SIZE * zoom_level)  # 0.5" radius highlight
    pygame.draw.circle(screen, (255, 255, 0), (enemy_screen_x, enemy_screen_y), 
                      enemy_highlight_radius, 3)  # Yellow highlight
    
    # Draw distance text if zoom level is reasonable
    if zoom_level > 0.5:
        font = pygame.font.Font(None, 24)
        
        # Distance text
        distance_text = f"{current_distance:.1f}\""
        text_surface = font.render(distance_text, True, (255, 255, 255))
        
        # Position text at midpoint of line
        mid_x = (model_screen_x + enemy_screen_x) // 2
        mid_y = (model_screen_y + enemy_screen_y) // 2 - 15
        
        # Background rectangle for text
        text_rect = text_surface.get_rect(center=(mid_x, mid_y))
        pygame.draw.rect(screen, (0, 0, 0, 180), text_rect.inflate(6, 4))
        screen.blit(text_surface, text_rect)
        
        # Enemy name text
        enemy_text = f"Closest: {enemy_name}"
        enemy_surface = font.render(enemy_text, True, (255, 255, 0))
        enemy_rect = enemy_surface.get_rect(center=(enemy_screen_x, enemy_screen_y - 40))
        pygame.draw.rect(screen, (0, 0, 0, 180), enemy_rect.inflate(6, 4))
        screen.blit(enemy_surface, enemy_rect)


# Old draw_movement_range function removed - now using Individual Model Movement Dialog for all movement


# Old draw_movement_path_preview function removed - now using Individual Model Movement Dialog for all movement


def draw_weapon_ranges(screen: pygame.Surface, unit, selected_weapon_profile, zoom_level: float, offset_x: int, offset_y: int) -> None:
    """Draw visual indicators showing the weapon range for each model that has the selected weapon"""
    if not selected_weapon_profile or not unit or not unit.models:
        return
    
    # TILE_SIZE is defined at the top of this file
    weapon_range = selected_weapon_profile.range.max
    if weapon_range <= 0:
        return  # Skip melee weapons
    
    # Choose color based on weapon type and special rules
    if selected_weapon_profile.is_pistol():
        range_color = (255, 100, 255, 64)  # Magenta for pistols
        border_color = (200, 50, 200)
    elif selected_weapon_profile.is_assault():
        range_color = (255, 255, 0, 64)  # Yellow for assault
        border_color = (200, 200, 0)  
    elif selected_weapon_profile.is_heavy():
        range_color = (255, 128, 0, 64)  # Orange for heavy
        border_color = (200, 100, 0)
    elif selected_weapon_profile.is_rapid_fire():
        range_color = (0, 255, 255, 64)  # Cyan for rapid fire
        border_color = (0, 200, 200)
    else:
        range_color = (0, 255, 0, 64)  # Green for other ranged weapons
        border_color = (0, 200, 0)
    
    # Draw range circle for each model that has this weapon
    models_with_weapon = []
    for model in unit.models:
        if not model.is_alive:
            continue
        
        # Check if this model has the selected weapon
        has_weapon = False
        for wargear in model.wargear:
            if wargear == selected_weapon_profile.parent_wargear:
                has_weapon = True
                break
        
        if has_weapon:
            models_with_weapon.append(model)
            
            # Get model position
            model_pos = model.get_location()
            
            # Convert model position to screen coordinates
            center_x = int(model_pos[0] * TILE_SIZE * zoom_level + offset_x)
            center_y = int(model_pos[1] * TILE_SIZE * zoom_level + offset_y)
            
            # Calculate radius in screen pixels
            radius = int(weapon_range * TILE_SIZE * zoom_level)
            
            if radius > 0:
                # Create a surface with per-pixel alpha for the range circle
                range_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(range_surface, range_color, (radius, radius), radius)
                
                # Blit the transparent range circle onto the battlefield
                screen.blit(range_surface, (center_x - radius, center_y - radius))
                
                # Draw the border circle with thinner line for individual models
                pygame.draw.circle(screen, border_color, (center_x, center_y), radius, 1)
    
    # Draw weapon information text
    if models_with_weapon:
        try:
            font = pygame.font.SysFont('Arial', max(14, int(16 * zoom_level)), bold=True)
            weapon_name = selected_weapon_profile.parent_wargear.name
            if len(selected_weapon_profile.parent_wargear.profiles) > 1:
                weapon_name += f"({selected_weapon_profile.name})"
            
            info_text = f"{weapon_name} - Range {weapon_range}\" ({len(models_with_weapon)} models)"
            text_surface = font.render(info_text, True, border_color)
            
            # Position text at top of screen
            text_rect = text_surface.get_rect()
            text_rect.center = (screen.get_width() // 2, 30)
            
            # Draw background for text
            bg_rect = text_rect.inflate(20, 10)
            pygame.draw.rect(screen, (0, 0, 0, 128), bg_rect)
            pygame.draw.rect(screen, border_color, bg_rect, 2)
            
            screen.blit(text_surface, text_rect)
        except:
            # Fallback if font creation fails
            pass
