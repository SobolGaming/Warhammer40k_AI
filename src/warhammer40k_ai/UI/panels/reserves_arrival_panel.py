"""
ReservesArrivalPanel component for handling unit arrival from reserves.
"""

import pygame
from typing import List, Optional, Tuple, Dict, Callable

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.engine.game import Game

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14
FONT_TINY = 12

# Modern UI Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_ACCENT = (100, 149, 237)  # Accent text

class ReservesArrivalPanel:
    """UI Panel for bringing units in from reserves during the game."""
    
    def __init__(self, width: int = 400, height: int = 500):
        self.width = width
        self.height = height
        self.visible = False
        self.player = None
        self.game = None
        self.available_units = []
        self.selected_unit = None
        self.placement_mode = False
        self.placement_position = None
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=False)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
            
        # Button dimensions
        self.unit_button_height = 60
        self.button_width = self.width - 40
        
        # Callbacks
        self.on_unit_placed = None
        self.on_cancel = None
        
    def show(self, player: Player, game: Game, on_unit_placed_callback: Callable, on_cancel_callback: Callable):
        """Show the reserves arrival panel."""
        self.visible = True
        self.player = player
        self.game = game
        self.on_unit_placed = on_unit_placed_callback
        self.on_cancel = on_cancel_callback
        
        # Get units that can arrive from reserves
        self.available_units = [unit for unit in player.get_army().units if unit.can_arrive_from_reserves(game.turn)]
        
    def hide(self):
        """Hide the reserves arrival panel."""
        self.visible = False
        self.placement_mode = False
        self.selected_unit = None
        self.placement_position = None
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events for the reserves arrival panel."""
        if not self.visible:
            return False
            
        if self.placement_mode:
            return self.handle_placement_event(event)
        else:
            return self.handle_selection_event(event)
            
    def handle_selection_event(self, event: pygame.event.Event) -> bool:
        """Handle events during unit selection."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_selection_click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
                
        return True
        
    def handle_placement_event(self, event: pygame.event.Event) -> bool:
        """Handle events during unit placement."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click to place
                if self.placement_position and self.is_valid_placement(self.placement_position):
                    if self.on_unit_placed:
                        self.on_unit_placed(self.selected_unit, self.placement_position)
                    self.hide()
                    return True
            elif event.button == 3:  # Right click to cancel
                self.placement_mode = False
                self.selected_unit = None
                return True
                
        elif event.type == pygame.MOUSEMOTION:
            # Update placement position
            game_x, game_y = self.screen_to_game_coords(event.pos)
            self.placement_position = (game_x, game_y, 0.0)
            return True
            
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.placement_mode = False
                self.selected_unit = None
                return True
                
        return True
        
    def handle_selection_click(self, mouse_pos: Tuple[int, int]) -> bool:
        """Handle mouse clicks during unit selection."""
        x, y = mouse_pos
        
        # Check unit buttons
        panel_x = 10  # Assume panel is positioned at left edge
        panel_y = 100  # Assume panel is positioned below other UI elements
        
        for i, unit in enumerate(self.available_units):
            unit_y = panel_y + 60 + i * (self.unit_button_height + 10)  # +60 for header
            unit_rect = pygame.Rect(panel_x + 20, unit_y, self.button_width, self.unit_button_height)
            
            if unit_rect.collidepoint(x, y):
                self.selected_unit = unit
                self.placement_mode = True
                return True
                
        # Check cancel button
        cancel_rect = pygame.Rect(panel_x + 20, panel_y + self.height - 50, 100, 30)
        if cancel_rect.collidepoint(x, y):
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True
            
        return True
        
    def screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates."""
        # This would need to be implemented based on the game's coordinate system
        # For now, return the screen position as-is
        return screen_pos[0], screen_pos[1]
        
    def is_valid_placement(self, position: Tuple[float, float, float]) -> bool:
        """Check if the placement position is valid for the selected unit."""
        if not self.selected_unit or not position:
            return False
            
        # Check reserves arrival rules
        if self.selected_unit.is_in_strategic_reserves():
            # Strategic Reserves units that also have Deep Strike may arrive using either ruleset.
            try:
                if self.selected_unit.has_deep_strike():
                    return self.is_valid_strategic_reserves_position(position) or self.is_valid_deep_strike_position(position)
            except Exception:
                pass
            return self.is_valid_strategic_reserves_position(position)
        else:
            # Standard reserves (Deep Strike) rules
            return self.is_valid_deep_strike_position(position)
            
    def is_valid_strategic_reserves_position(self, position: Tuple[float, float, float]) -> bool:
        """Check if position is valid for strategic reserves arrival."""
        # Must be within 6" of battlefield edge and more than 9" from enemies
        # This is a simplified check - full implementation would need game map
        return True
        
    def is_valid_deep_strike_position(self, position: Tuple[float, float, float]) -> bool:
        """Check if position is valid for deep strike arrival."""
        # Must be more than 9" from enemy models
        # This is a simplified check - full implementation would need game map
        return True
        
    def draw(self, screen: pygame.Surface):
        """Draw the reserves arrival panel."""
        if not self.visible:
            return
            
        if self.placement_mode:
            self.draw_placement_mode(screen)
        else:
            self.draw_selection_mode(screen)
            
    def draw_selection_mode(self, screen: pygame.Surface):
        """Draw the unit selection interface."""
        panel_x = 10
        panel_y = 100
        panel_rect = pygame.Rect(panel_x, panel_y, self.width, self.height)
        
        # Draw panel background
        pygame.draw.rect(screen, PANEL_BG, panel_rect)
        pygame.draw.rect(screen, PANEL_BORDER, panel_rect, 2)
        
        # Draw header
        header_text = self.font_large.render("Reserves Arrival", True, TEXT_PRIMARY)
        screen.blit(header_text, (panel_x + 20, panel_y + 20))
        
        # Draw turn info
        turn_info = f"Turn {self.game.turn} - {self.player.name}"
        turn_text = self.font_medium.render(turn_info, True, TEXT_SECONDARY)
        screen.blit(turn_text, (panel_x + 20, panel_y + 45))
        
        # Draw units
        if not self.available_units:
            no_units_text = self.font_medium.render("No units available", True, TEXT_SECONDARY)
            screen.blit(no_units_text, (panel_x + 20, panel_y + 80))
        else:
            for i, unit in enumerate(self.available_units):
                unit_y = panel_y + 60 + i * (self.unit_button_height + 10)
                self.draw_reserves_unit_button(screen, unit, panel_x + 20, unit_y)
                
        # Draw cancel button
        cancel_rect = pygame.Rect(panel_x + 20, panel_y + self.height - 50, 100, 30)
        pygame.draw.rect(screen, BUTTON_BG, cancel_rect)
        cancel_text = self.font_medium.render("Cancel", True, TEXT_PRIMARY)
        screen.blit(cancel_text, (cancel_rect.left + 10, cancel_rect.top + 5))
        
    def draw_placement_mode(self, screen: pygame.Surface):
        """Draw the unit placement interface."""
        # Draw placement preview
        if self.placement_position:
            self.draw_placement_preview(screen)
            
        # Draw instructions
        instruction_text = "Left click to place unit, right click to cancel"
        instruction_surface = self.font_medium.render(instruction_text, True, TEXT_PRIMARY)
        screen.blit(instruction_surface, (10, 10))
        
    def draw_placement_preview(self, screen: pygame.Surface):
        """Draw preview of unit placement."""
        if not self.placement_position:
            return
            
        # Draw unit preview at placement position
        x, y, _ = self.placement_position
        preview_rect = pygame.Rect(x - 20, y - 20, 40, 40)
        
        # Draw with different colors based on placement validity
        if self.is_valid_placement(self.placement_position):
            color = (0, 255, 0, 128)  # Green for valid
        else:
            color = (255, 0, 0, 128)  # Red for invalid
            
        pygame.draw.rect(screen, color, preview_rect, 2)
        
    def draw_reserves_unit_button(self, screen: pygame.Surface, unit: Unit, x: int, y: int):
        """Draw a button for a reserves unit."""
        button_rect = pygame.Rect(x, y, self.button_width, self.unit_button_height)
        
        # Draw button background
        pygame.draw.rect(screen, BUTTON_BG, button_rect)
        pygame.draw.rect(screen, PANEL_BORDER, button_rect, 2)
        
        # Draw unit name
        name_text = self.font_medium.render(unit.name, True, TEXT_PRIMARY)
        screen.blit(name_text, (x + 10, y + 10))
        
        # Draw unit type and arrival type
        try:
            if unit.is_in_strategic_reserves() and unit.has_deep_strike():
                type_text = "Strategic Reserves (or Deep Strike)"
            else:
                type_text = "Strategic Reserves" if unit.is_in_strategic_reserves() else "Deep Strike"
        except Exception:
            type_text = "Strategic Reserves" if unit.is_in_strategic_reserves() else "Deep Strike"
        type_surface = self.font_small.render(type_text, True, TEXT_SECONDARY)
        screen.blit(type_surface, (x + 10, y + 35)) 