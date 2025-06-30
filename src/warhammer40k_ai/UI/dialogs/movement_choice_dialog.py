import pygame
from typing import List

# Font sizes
FONT_MEDIUM = 16
FONT_SMALL = 14

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_DISABLED = (100, 100, 100)  # Disabled text


class MovementChoiceDialog:
    """Dialog for choosing movement option for a unit during movement phase"""
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 520
        self.height = 220
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_actions = []
        
        # Calculate position (center of screen)
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        # Fonts
        try:
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
        
        # Button rectangles
        button_width = 95
        button_height = 32
        button_spacing = 12
        
        start_x = self.x + (self.width - (4 * button_width + 3 * button_spacing)) // 2
        button_y = self.y + self.height - 120
        
        self.move_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.advance_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        self.fall_back_button = pygame.Rect(start_x + 2 * (button_width + button_spacing), button_y, button_width, button_height)
        self.stationary_button = pygame.Rect(start_x + 3 * (button_width + button_spacing), button_y, button_width, button_height)
        
        self.hovered_button = None
    
    def show(self, unit, callback, game_map=None):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.visible = True
        
        # Get available actions based on engagement state
        if game_map:
            engagement_state = unit.get_engagement_state(game_map)
            self.available_actions = unit.get_available_move_actions(engagement_state.value)
        else:
            # Fallback - assume all actions available
            from warhammer40k_ai.classes.unit import MovementAction
            self.available_actions = [
                MovementAction.REMAIN_STATIONARY.value,
                MovementAction.MOVE.value,
                MovementAction.ADVANCE.value,
                MovementAction.FALL_BACK.value
            ]
    
    def hide(self):
        """Hide the dialog"""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_actions = []
    
    def is_action_available(self, action_name: str) -> bool:
        """Check if a movement action is available for the current unit"""
        from warhammer40k_ai.classes.unit import MovementAction
        
        action_map = {
            'move': MovementAction.MOVE.value,
            'advance': MovementAction.ADVANCE.value,
            'fall_back': MovementAction.FALL_BACK.value,
            'stationary': MovementAction.REMAIN_STATIONARY.value
        }
        
        if action_name not in action_map:
            return False
            
        return action_map[action_name] in self.available_actions
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
        
        return True  # Consume all events when visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        if self.move_button.collidepoint(mouse_pos) and self.is_action_available('move'):
            if self.callback:
                self.callback('move')
            self.hide()
            return True
        elif self.advance_button.collidepoint(mouse_pos) and self.is_action_available('advance'):
            if self.callback:
                self.callback('advance')
            self.hide()
            return True
        elif self.fall_back_button.collidepoint(mouse_pos) and self.is_action_available('fall_back'):
            if self.callback:
                self.callback('fall_back')
            self.hide()
            return True
        elif self.stationary_button.collidepoint(mouse_pos) and self.is_action_available('stationary'):
            if self.callback:
                self.callback('stationary')
            self.hide()
            return True
        
        # Click outside dialog - close it
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            self.hide()
            return True
        
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        if self.move_button.collidepoint(mouse_pos):
            self.hovered_button = 'move'
        elif self.advance_button.collidepoint(mouse_pos):
            self.hovered_button = 'advance'
        elif self.fall_back_button.collidepoint(mouse_pos):
            self.hovered_button = 'fall_back'
        elif self.stationary_button.collidepoint(mouse_pos):
            self.hovered_button = 'stationary'
        else:
            self.hovered_button = None
    
    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            return
        
        # Draw semi-transparent overlay only around the dialog area
        overlay = pygame.Surface((self.width + 40, self.height + 40))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (self.x - 20, self.y - 20))
        
        # Draw dialog background
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, PANEL_BG, dialog_rect)
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 3)
        
        # Draw title
        title_text = self.font_medium.render(f"Move {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw movement info
        movement_info = f"Movement: {self.unit.models[0].movement}\""
        info_text = self.font_small.render(movement_info, True, TEXT_SECONDARY)
        info_rect = info_text.get_rect(center=(self.x + self.width // 2, self.y + 55))
        screen.blit(info_text, info_rect)
        
        # Draw buttons - only enabled if action is available
        self.draw_button(screen, self.move_button, "Move", 'move', BUTTON_BG, enabled=self.is_action_available('move'))
        self.draw_button(screen, self.advance_button, "Advance", 'advance', BUTTON_BG, enabled=self.is_action_available('advance'))
        self.draw_button(screen, self.fall_back_button, "Fall Back", 'fall_back', BUTTON_BG, enabled=self.is_action_available('fall_back'))
        self.draw_button(screen, self.stationary_button, "Stationary", 'stationary', BUTTON_BG, enabled=self.is_action_available('stationary'))
        
        # Draw help text based on available actions
        help_parts = []
        if self.is_action_available('move'):
            help_parts.append("Move: Normal")
        if self.is_action_available('advance'):
            help_parts.append("Advance: +D6\" no shoot")
        if self.is_action_available('fall_back'):
            help_parts.append("Fall Back: Exit combat")
        
        if help_parts:
            help_text = " | ".join(help_parts)
        else:
            help_text = "Only Stationary available"
            
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        help_rect = help_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 30))
        screen.blit(help_surface, help_rect)
    
    def draw_button(self, screen, rect, text, button_id, base_color, enabled=True):
        """Draw a button with hover effects"""
        if not enabled:
            color = BUTTON_DISABLED
            text_color = TEXT_DISABLED
        elif self.hovered_button == button_id:
            color = BUTTON_HOVER
            text_color = TEXT_PRIMARY
        else:
            color = base_color
            text_color = TEXT_PRIMARY
        
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, PANEL_BORDER, rect, 2)
        
        button_text = self.font_small.render(text, True, text_color)
        text_rect = button_text.get_rect(center=rect.center)
        screen.blit(button_text, text_rect) 