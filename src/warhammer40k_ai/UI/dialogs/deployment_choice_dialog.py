import pygame

# Font sizes
FONT_MEDIUM = 16
FONT_SMALL = 14

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
DEPLOY_BUTTON_BG = (70, 130, 70)  # Green for deploy
RESERVES_BUTTON_BG = (70, 70, 130)  # Blue for reserves
STRATEGIC_BUTTON_BG = (130, 70, 130)  # Purple for strategic
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_DISABLED = (100, 100, 100)  # Disabled text


class DeploymentChoiceDialog:
    """Simple dialog for choosing deployment option for a single unit"""
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 300
        self.height = 250  # Increased height for reserve limits display
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_view = None  # Reference to game view for army access
        
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
        button_width = 80
        button_height = 30
        button_spacing = 10
        
        start_x = self.x + (self.width - (3 * button_width + 2 * button_spacing)) // 2
        button_y = self.y + self.height - 110
        
        self.deploy_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.reserves_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        self.strategic_button = pygame.Rect(start_x + 2 * (button_width + button_spacing), button_y, button_width, button_height)
        
        self.hovered_button = None
    
    def can_add_to_reserves(self, reserve_type):
        """Check if the unit can be added to reserves without exceeding limits."""
        if not self.game_view or not self.unit:
            return False
        
        # Find the player that owns this unit
        player = None
        if self.unit in self.game_view.player1.get_army().units:
            player = self.game_view.player1
        elif self.unit in self.game_view.player2.get_army().units:
            player = self.game_view.player2
        
        if not player:
            return False
        
        army = player.get_army()
        
        # Calculate current reserves
        current_reserve_units = 0
        current_reserve_points = 0
        for unit_obj in army.units:
            if unit_obj.reserve_status in ['reserves', 'strategic_reserves']:
                current_reserve_units += 1
                current_reserve_points += unit_obj.get_unit_cost()
        
        # Check if adding this unit would exceed limits
        return army.can_add_unit_to_reserves(self.unit, current_reserve_units, current_reserve_points)
    
    def get_current_reserves_status(self):
        """Get current reserves status for display."""
        if not self.game_view or not self.unit:
            return None
        
        # Find the player that owns this unit
        player = None
        if self.unit in self.game_view.player1.get_army().units:
            player = self.game_view.player1
        elif self.unit in self.game_view.player2.get_army().units:
            player = self.game_view.player2
        
        if not player:
            return None
        
        army = player.get_army()
        
        # Calculate current reserves
        current_reserve_units = 0
        current_reserve_points = 0
        for unit_obj in army.units:
            if unit_obj.reserve_status in ['reserves', 'strategic_reserves']:
                current_reserve_units += 1
                current_reserve_points += unit_obj.get_unit_cost()
        
        limits = army.get_reserve_limits()
        return {
            'reserve_units': current_reserve_units,
            'reserve_points': current_reserve_points,
            'limits': limits
        }
    
    def show(self, unit, callback, game_view=None):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_view = game_view
        self.visible = True
    
    def hide(self):
        """Hide the dialog"""
        self.visible = False
        self.unit = None
        self.callback = None
    
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
        if self.deploy_button.collidepoint(mouse_pos):
            if self.callback:
                self.callback('deploy')
            self.hide()
            return True
        elif self.reserves_button.collidepoint(mouse_pos):
            # Only allow reserves if unit has Deep Strike and limits allow
            can_reserves = self.unit and self.unit.has_deep_strike() and self.can_add_to_reserves('reserves')
            print(f"🔍 DEBUG: {self.unit.name} reserves check - Deep Strike: {self.unit.has_deep_strike()}, Can add: {self.can_add_to_reserves('reserves')}")
            if can_reserves:
                if self.callback:
                    self.callback('reserves')
                self.hide()
                return True
            # If unit doesn't have Deep Strike or limits exceeded, don't do anything but still consume the click
            return True
        elif self.strategic_button.collidepoint(mouse_pos):
            # Only allow strategic reserves if limits allow
            if self.can_add_to_reserves('strategic_reserves'):
                if self.callback:
                    self.callback('strategic_reserves')
                self.hide()
                return True
            # If limits exceeded, don't do anything but still consume the click
            return True
        
        # Click outside dialog - close it
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            self.hide()
            return True
        
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        if self.deploy_button.collidepoint(mouse_pos):
            self.hovered_button = 'deploy'
        elif self.reserves_button.collidepoint(mouse_pos):
            self.hovered_button = 'reserves'
        elif self.strategic_button.collidepoint(mouse_pos):
            self.hovered_button = 'strategic'
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
        title_text = self.font_medium.render(f"Deploy {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw instruction
        instruction = "Choose deployment option:"
        instruction_text = self.font_small.render(instruction, True, TEXT_SECONDARY)
        instruction_rect = instruction_text.get_rect(center=(self.x + self.width // 2, self.y + 60))
        screen.blit(instruction_text, instruction_rect)
        
        # Draw buttons
        self.draw_button(screen, self.deploy_button, "Deploy", 'deploy', DEPLOY_BUTTON_BG)
        
        # Reserves button - only enabled if unit has Deep Strike and limits allow
        can_reserves = self.unit.has_deep_strike() and self.can_add_to_reserves('reserves')
        if can_reserves:
            self.draw_button(screen, self.reserves_button, "Reserves", 'reserves', RESERVES_BUTTON_BG)
        else:
            self.draw_button(screen, self.reserves_button, "Reserves", 'reserves', BUTTON_DISABLED, enabled=False)
        
        # Strategic reserves button - only enabled if limits allow
        can_strategic = self.can_add_to_reserves('strategic_reserves')
        if can_strategic:
            self.draw_button(screen, self.strategic_button, "Strategic", 'strategic', STRATEGIC_BUTTON_BG)
        else:
            self.draw_button(screen, self.strategic_button, "Strategic", 'strategic', BUTTON_DISABLED, enabled=False)
        
        # Draw reserve limits status
        status = self.get_current_reserves_status()
        if status:
            limits_text = f"Reserves: {status['reserve_units']}/{status['limits']['max_units']} units, {status['reserve_points']}/{status['limits']['max_points']} pts"
            limits_surface = self.font_small.render(limits_text, True, TEXT_SECONDARY)
            limits_rect = limits_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 60))
            screen.blit(limits_surface, limits_rect)
        
        # Draw help text
        if not self.unit.has_deep_strike():
            help_text = "Reserves: Requires Deep Strike ability"
        elif not self.can_add_to_reserves('reserves'):
            help_text = "Reserves: Limits exceeded"
        elif not self.can_add_to_reserves('strategic_reserves'):
            help_text = "Strategic: Limits exceeded"
        else:
            help_text = "Reserves: Deep Strike ability required"
        
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        help_rect = help_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 40))
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