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


class ScoutChoiceDialog:
    """Dialog for choosing scout move option for a unit during pre-battle rules phase"""
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 400
        self.height = 200
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.scout_distance = 0.0
        
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
        
        # Button dimensions (will be positioned in show() method)
        self.button_width = 120
        self.button_height = 40
        self.button_spacing = 20

        # Initialize button rectangles (will be updated in show())
        self.scout_button = pygame.Rect(0, 0, self.button_width, self.button_height)
        self.skip_button = pygame.Rect(0, 0, self.button_width, self.button_height)
        
        self.hovered_button = None
    
    def show(self, unit, callback, game_map=None):
        """Show the dialog for the given unit"""
        print(f"🔍 ScoutChoiceDialog.show called for {unit.name}")
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.visible = True
        print(f"🔍 DEBUG: ScoutChoiceDialog.visible set to {self.visible}")

        # Update button positions based on current dialog position
        start_x = self.x + (self.width - (2 * self.button_width + self.button_spacing)) // 2
        button_y = self.y + self.height - 100

        self.scout_button = pygame.Rect(start_x, button_y, self.button_width, self.button_height)
        self.skip_button = pygame.Rect(start_x + self.button_width + self.button_spacing, button_y, self.button_width, self.button_height)

        print(f"🔍 DEBUG: Button positions - Scout: {self.scout_button}, Skip: {self.skip_button}")

        # Get scout distance from unit
        has_scout, scout_distance = unit.has_scout()
        print(f"🔍 {unit.name} has_scout={has_scout}, scout_distance={scout_distance}")
        if has_scout:
            self.scout_distance = scout_distance
        else:
            self.scout_distance = 0.0
        print(f"🔍 DEBUG: ScoutChoiceDialog.show completed for {unit.name}")
    
    def hide(self):
        """Hide the dialog"""
        print(f"🔍 DEBUG: ScoutChoiceDialog.hide called")
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.scout_distance = 0.0
    
    def can_scout(self) -> bool:
        """Check if the unit can make a scout move"""
        if not self.unit:
            print("🔍 can_scout: No unit")
            return False
        
        # Check if unit has scout ability
        has_scout, _ = self.unit.has_scout()
        if not has_scout:
            print(f"🔍 can_scout: {self.unit.name} has no scout ability")
            return False
        
        # Check if unit is deployed (not in reserves)
        if not self.unit.deployed or self.unit.reserve_status != 'deployed':
            print(f"🔍 can_scout: {self.unit.name} not deployed (deployed={self.unit.deployed}, reserve_status={self.unit.reserve_status})")
            return False
        
        # Check if unit hasn't already made a scout move
        if hasattr(self.unit, 'scout_move_made') and self.unit.scout_move_made:
            print(f"🔍 can_scout: {self.unit.name} already made scout move")
            return False
        
        #print(f"🔍 can_scout: {self.unit.name} can scout")
        return True
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            print(f"🔍 DEBUG: ScoutChoiceDialog.handle_event called but not visible")
            return False

        # Debug: Log all events handled by this dialog
        dialog_name = self.__class__.__name__
        if event.type == pygame.KEYDOWN:
            print(f"🔍 DEBUG: {dialog_name}.handle_event - KEYDOWN: key={pygame.key.name(event.key)}")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEBUTTONDOWN: button={event.button}, pos={event.pos}")
        elif event.type == pygame.MOUSEBUTTONUP:
            print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEBUTTONUP: button={event.button}, pos={event.pos}")
        elif event.type == pygame.MOUSEMOTION:
            print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEMOTION: pos={event.pos}")
        else:
            print(f"🔍 DEBUG: {dialog_name}.handle_event - OTHER: type={event.type}")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            print(f"🔍 DEBUG: {dialog_name} - Left click, delegating to handle_click")
            return self.handle_click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print(f"🔍 DEBUG: {dialog_name} - ESC key pressed, deferring decision")
                # ESC should defer the decision - move unit to end of queue
                callback = self.callback  # Store callback before hide() clears it
                self.hide()
                if callback:
                    print(f"🔍 DEBUG: Calling callback with 'defer'")
                    callback('defer')
                return True
            elif event.key == pygame.K_s and self.can_scout():
                print(f"🔍 DEBUG: {dialog_name} - 'S' key pressed for Scout")
                # 'S' key for Scout
                callback = self.callback  # Store callback before hide() clears it
                self.hide()
                if callback:
                    callback('scout')
                return True
            elif event.key == pygame.K_k:
                print(f"🔍 DEBUG: {dialog_name} - 'K' key pressed for Skip")
                # 'K' key for Skip
                callback = self.callback  # Store callback before hide() clears it
                self.hide()
                if callback:
                    callback('skip')
                return True

        return True  # Consume all events when visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        print(f"🔍 DEBUG: ScoutChoiceDialog.handle_click called with mouse_pos={mouse_pos}")
        print(f"🔍 DEBUG: Scout button rect: {self.scout_button}")
        print(f"🔍 DEBUG: Skip button rect: {self.skip_button}")
        print(f"🔍 DEBUG: Scout button collision: {self.scout_button.collidepoint(mouse_pos)}")
        print(f"🔍 DEBUG: Skip button collision: {self.skip_button.collidepoint(mouse_pos)}")
        print(f"🔍 DEBUG: Can scout: {self.can_scout()}")

        if self.scout_button.collidepoint(mouse_pos) and self.can_scout():
            print(f"🔍 DEBUG: Scout button clicked")
            callback = self.callback  # Store callback before hide() clears it
            self.hide()
            if callback:
                callback('scout')
            return True
        elif self.skip_button.collidepoint(mouse_pos):
            print(f"🔍 DEBUG: Skip button clicked")
            callback = self.callback  # Store callback before hide() clears it
            self.hide()
            if callback:
                callback('skip')
            return True
        
        # Click outside dialog - defer decision (same as ESC)
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            print(f"🔍 DEBUG: Click outside dialog, deferring decision")
            callback = self.callback  # Store callback before hide() clears it
            self.hide()
            if callback:
                print(f"🔍 DEBUG: Calling callback with 'defer'")
                callback('defer')
            return True
        
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        if self.scout_button.collidepoint(mouse_pos):
            self.hovered_button = 'scout'
        elif self.skip_button.collidepoint(mouse_pos):
            self.hovered_button = 'skip'
        else:
            self.hovered_button = None
    
    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            print(f"🔍 DEBUG: ScoutChoiceDialog.draw called but not visible or no unit")
            return
        
        print(f"🔍 DEBUG: Drawing scout dialog for {self.unit.name}")
        
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
        title_text = self.font_medium.render(f"Scout Move - {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw scout info
        scout_info = f"Scout Distance: {self.scout_distance}\""
        info_text = self.font_small.render(scout_info, True, TEXT_SECONDARY)
        info_rect = info_text.get_rect(center=(self.x + self.width // 2, self.y + 55))
        screen.blit(info_text, info_rect)
        
        # Draw restrictions info
        restrictions_text = "Cannot end within 9\" of enemy units"
        restrictions_surface = self.font_small.render(restrictions_text, True, TEXT_SECONDARY)
        restrictions_rect = restrictions_surface.get_rect(center=(self.x + self.width // 2, self.y + 75))
        screen.blit(restrictions_surface, restrictions_rect)
        
        # Draw buttons
        self.draw_button(screen, self.scout_button, "Scout", 'scout', BUTTON_BG, enabled=self.can_scout())
        self.draw_button(screen, self.skip_button, "Skip", 'skip', BUTTON_BG, enabled=True)
        
        # Draw help text
        help_text = "Press 'S' for Scout, 'K' for Skip, or ESC to cancel"
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        help_rect = help_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 20))
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