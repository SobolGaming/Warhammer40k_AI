import pygame
from typing import Dict

# Font sizes
FONT_LARGE = 20
FONT_MEDIUM = 16
FONT_SMALL = 14

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
DEPLOY_BUTTON_BG = (70, 130, 70)  # Green for deploy
RESERVES_BG = (70, 70, 130)  # Blue for reserves
STRATEGIC_RESERVES_BG = (130, 70, 130)  # Purple for strategic reserves
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
DARK_GREY = (40, 40, 40)
LIGHT_GREY = (160, 160, 160)


class ReservesSelectionDialog:
    """
    Dialog for selecting which units go into reserves during deployment setup.
    """
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 800
        self.height = 600
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        self.visible = False
        self.player = None
        self.on_complete = None
        self.unit_choices = {}  # unit_id -> choice ('deploy', 'reserves', 'strategic_reserves')
        self.scroll_offset = 0
        self.max_scroll = 0
        self.hovered_unit = None
        
        # Choice button dimensions
        self.choice_button_width = 100
        self.choice_button_height = 25
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
    
    def show(self, player, on_complete_callback):
        """Show the reserves selection dialog."""
        self.visible = True
        self.player = player
        self.on_complete = on_complete_callback
        
        # Initialize all units to deploy by default
        self.unit_choices = {}
        for unit in player.get_army().units:
            self.unit_choices[unit.id] = 'deploy'
        
        # Calculate scroll limits
        unit_count = len(player.get_army().units)
        total_height = unit_count * 80  # 80 pixels per unit
        visible_height = self.height - 120  # Account for header and buttons
        self.max_scroll = max(0, total_height - visible_height)
    
    def hide(self):
        """Hide the dialog."""
        self.visible = False
        self.player = None
        self.on_complete = None
        self.unit_choices = {}
        self.scroll_offset = 0
    
    def handle_event(self, event):
        """Handle pygame events."""
        if not self.visible:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                return self.handle_click(event.pos)
            elif event.button == 4:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 30)
                return True
            elif event.button == 5:  # Scroll down
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 30)
                return True
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            elif event.key == pygame.K_RETURN:
                self.complete_selection()
                return True
        
        return True  # Consume all events when visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks."""
        x, y = mouse_pos
        
        # Check if clicking on unit choice buttons
        units = list(self.player.get_army().units)
        for i, unit in enumerate(units):
            unit_y = self.y + 70 + i * 80 - self.scroll_offset
            
            # Skip units that are outside visible area
            if unit_y < self.y + 60 or unit_y > self.y + self.height - 80:
                continue
                
            choice_y = unit_y + 35
            
            # Deploy button
            deploy_rect = pygame.Rect(self.x + 30, choice_y, self.choice_button_width, self.choice_button_height)
            if deploy_rect.collidepoint(x, y):
                self.unit_choices[unit.id] = 'deploy'
                return True
            
            # Reserves button (only if unit can use reserves)
            reserves_rect = pygame.Rect(self.x + 30 + self.choice_button_width + 10, choice_y, self.choice_button_width, self.choice_button_height)
            if reserves_rect.collidepoint(x, y) and self.can_use_reserves(unit):
                self.unit_choices[unit.id] = 'reserves'
                return True
            
            # Strategic reserves button
            strategic_rect = pygame.Rect(self.x + 30 + 2 * (self.choice_button_width + 10), choice_y, self.choice_button_width, self.choice_button_height)
            if strategic_rect.collidepoint(x, y):
                self.unit_choices[unit.id] = 'strategic_reserves'
                return True
        
        # Check complete button
        complete_rect = pygame.Rect(self.x + self.width - 120, self.y + self.height - 50, 100, 30)
        if complete_rect.collidepoint(x, y):
            self.complete_selection()
            return True
        
        # Click outside - don't close automatically, let user explicitly finish
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state."""
        x, y = mouse_pos
        self.hovered_unit = None
        
        units = list(self.player.get_army().units)
        for i, unit in enumerate(units):
            unit_y = self.y + 70 + i * 80 - self.scroll_offset
            unit_rect = pygame.Rect(self.x + 20, unit_y, self.width - 40, 70)
            
            if unit_rect.collidepoint(x, y):
                self.hovered_unit = unit.id
                break
    
    def can_use_reserves(self, unit):
        """Check if a unit can use standard reserves (Deep Strike)."""
        return unit.has_deep_strike()
    
    def complete_selection(self):
        """Complete the reserves selection."""
        if self.on_complete:
            self.on_complete(self.unit_choices)
        self.hide()
    
    def draw(self, screen):
        """Draw the reserves selection dialog."""
        if not self.visible:
            return
        
        # Draw dialog background
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, PANEL_BG, dialog_rect)
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 3)
        
        # Draw title
        title_text = self.font_large.render("Reserve Deployment Selection", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 25))
        screen.blit(title_text, title_rect)
        
        # Draw instructions
        instruction = f"Choose deployment for {self.player.name}'s units"
        instruction_text = self.font_medium.render(instruction, True, TEXT_SECONDARY)
        instruction_rect = instruction_text.get_rect(center=(self.x + self.width // 2, self.y + 50))
        screen.blit(instruction_text, instruction_rect)
        
        # Create clipping area for scrollable content
        content_rect = pygame.Rect(self.x + 10, self.y + 70, self.width - 20, self.height - 140)
        screen.set_clip(content_rect)
        
        # Draw units
        units = list(self.player.get_army().units)
        for i, unit in enumerate(units):
            unit_y = self.y + 70 + i * 80 - self.scroll_offset
            self.draw_unit_selection(screen, unit, unit_y)
        
        # Remove clipping
        screen.set_clip(None)
        
        # Draw complete button
        complete_rect = pygame.Rect(self.x + self.width - 120, self.y + self.height - 50, 100, 30)
        pygame.draw.rect(screen, BUTTON_BG, complete_rect)
        pygame.draw.rect(screen, PANEL_BORDER, complete_rect, 2)
        
        complete_text = self.font_medium.render("Complete", True, TEXT_PRIMARY)
        text_rect = complete_text.get_rect(center=complete_rect.center)
        screen.blit(complete_text, text_rect)
        
        # Draw scroll indicator if needed
        if self.max_scroll > 0:
            self.draw_scroll_indicator(screen)
    
    def draw_unit_selection(self, screen, unit, y):
        """Draw unit selection row."""
        current_choice = self.unit_choices.get(unit.id, 'deploy')
        
        # Unit background
        unit_rect = pygame.Rect(self.x + 20, y, self.width - 40, 70)
        bg_color = BUTTON_HOVER if self.hovered_unit == unit.id else PANEL_BG
        pygame.draw.rect(screen, bg_color, unit_rect)
        pygame.draw.rect(screen, PANEL_BORDER, unit_rect, 1)
        
        # Unit name
        unit_name = f"{unit.name} ({unit.get_unit_cost()} pts)"
        name_text = self.font_medium.render(unit_name, True, TEXT_PRIMARY)
        screen.blit(name_text, (self.x + 30, y + 5))
        
        # Unit keywords (for context about Deep Strike capability)
        if unit.keywords:
            keywords_str = ", ".join(unit.keywords[:3])  # Show first 3 keywords
            if len(unit.keywords) > 3:
                keywords_str += "..."
            keywords_text = self.font_small.render(keywords_str, True, TEXT_SECONDARY)
            screen.blit(keywords_text, (self.x + 30, y + 25))
        
        # Choice buttons
        choice_y = y + 35
        
        # Deploy button
        deploy_color = DEPLOY_BUTTON_BG if current_choice == 'deploy' else BUTTON_BG
        deploy_rect = pygame.Rect(self.x + 30, choice_y, self.choice_button_width, self.choice_button_height)
        pygame.draw.rect(screen, deploy_color, deploy_rect)
        pygame.draw.rect(screen, PANEL_BORDER, deploy_rect, 1)
        
        deploy_text = self.font_small.render("Deploy", True, TEXT_PRIMARY)
        text_rect = deploy_text.get_rect(center=deploy_rect.center)
        screen.blit(deploy_text, text_rect)
        
        # Reserves button
        can_reserves = self.can_use_reserves(unit)
        reserves_color = RESERVES_BG if current_choice == 'reserves' else BUTTON_BG
        if not can_reserves:
            reserves_color = DARK_GREY
        
        reserves_rect = pygame.Rect(self.x + 30 + self.choice_button_width + 10, choice_y, self.choice_button_width, self.choice_button_height)
        pygame.draw.rect(screen, reserves_color, reserves_rect)
        pygame.draw.rect(screen, PANEL_BORDER, reserves_rect, 1)
        
        reserves_text = self.font_small.render("Reserves", True, TEXT_PRIMARY if can_reserves else TEXT_SECONDARY)
        text_rect = reserves_text.get_rect(center=reserves_rect.center)
        screen.blit(reserves_text, text_rect)
        
        # Strategic reserves button
        strategic_rect = pygame.Rect(self.x + 30 + 2 * (self.choice_button_width + 10), choice_y, self.choice_button_width, self.choice_button_height)
        strategic_color = STRATEGIC_RESERVES_BG if current_choice == 'strategic_reserves' else BUTTON_BG
        pygame.draw.rect(screen, strategic_color, strategic_rect)
        pygame.draw.rect(screen, PANEL_BORDER, strategic_rect, 1)
        
        strategic_text = self.font_small.render("Strategic Reserves", True, TEXT_PRIMARY)
        text_rect = strategic_text.get_rect(center=strategic_rect.center)
        screen.blit(strategic_text, text_rect)
        
    def draw_scroll_indicator(self, screen):
        """Draw scroll indicator."""
        if self.max_scroll <= 0:
            return
            
        # Scroll bar background
        scroll_rect = pygame.Rect(self.x + self.width - 15, self.y + 70, 10, self.height - 120)
        pygame.draw.rect(screen, DARK_GREY, scroll_rect)
        
        # Scroll thumb
        thumb_height = max(20, int((self.height - 120) * (self.height - 120) / (self.max_scroll + self.height - 120)))
        thumb_y = self.y + 70 + int(self.scroll_offset * (self.height - 120 - thumb_height) / self.max_scroll)
        thumb_rect = pygame.Rect(self.x + self.width - 15, thumb_y, 10, thumb_height)
        pygame.draw.rect(screen, LIGHT_GREY, thumb_rect) 