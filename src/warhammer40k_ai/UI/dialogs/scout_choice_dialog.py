import pygame
from typing import List
from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, BUTTON_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED


class ScoutChoiceDialog(BaseDialog):
    """Dialog for choosing scout move option for a unit during pre-battle rules phase"""
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=420, height=220, draggable=True, center=True)
        self.unit = None
        self.callback = None
        self.game_map = None
        self.scout_distance = 0.0
    
    def show(self, unit, callback, game_map=None):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        super().show(callback)
        self._create_buttons()

        # Get scout distance from unit
        has_scout, scout_distance = unit.has_scout()
        if has_scout:
            self.scout_distance = scout_distance
        else:
            self.scout_distance = 0.0
        # print(f"🔍 DEBUG: ScoutChoiceDialog.show completed for {unit.name}")
    
    def hide(self):
        """Hide the dialog"""
        super().hide()
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
            return False
        if super().handle_event(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_click(event.pos)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                cb = self.callback
                self.hide()
                if cb:
                    cb('defer')
                return True
            if event.key == pygame.K_s and self.can_scout():
                cb = self.callback
                self.hide()
                if cb:
                    cb('scout')
                return True
            if event.key == pygame.K_k:
                cb = self.callback
                self.hide()
                if cb:
                    cb('skip')
                return True
        return False
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        if 'scout' in self.buttons and self.buttons['scout'].collidepoint(mouse_pos) and self.can_scout():
            cb = self.callback
            self.hide()
            if cb:
                cb('scout')
            return True
        if 'skip' in self.buttons and self.buttons['skip'].collidepoint(mouse_pos):
            cb = self.callback
            self.hide()
            if cb:
                cb('skip')
            return True

        # Click outside dialog - defer decision (same as ESC)
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            # print(f"🔍 DEBUG: Click outside dialog, deferring decision")
            cb = self.callback
            self.hide()
            if cb:
                cb('defer')
            return True
        
        return True
    
    def update_hover(self, mouse_pos):
        """Update hover state"""
        self.hovered_button = None
        for name, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                self.hovered_button = name
                break
    
    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            # print(f"🔍 DEBUG: ScoutChoiceDialog.draw called but not visible or no unit")
            return
        
        # Dialog background & title
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, f"Scout Move - {self.unit.name}")
        
        # Text block under title: consistent left alignment and spacing
        content_x = self.x + 20
        cur_y = self.y + self.title_bar_height + 12

        # Line 1: Scout distance
        scout_info = f"Scout Distance: {self.scout_distance}\""
        info_text = self.font_small.render(scout_info, True, TEXT_SECONDARY)
        screen.blit(info_text, (content_x, cur_y))
        cur_y += self.font_small.get_linesize() + 6

        # Line 2: Restrictions
        restrictions_text = "Cannot end within 9\" of enemy units"
        restrictions_surface = self.font_small.render(restrictions_text, True, TEXT_SECONDARY)
        screen.blit(restrictions_surface, (content_x, cur_y))
        cur_y += self.font_small.get_linesize() + 6
        
        # Draw buttons
        self._create_buttons()
        self.draw_button(screen, 'scout', 'Scout', color=BUTTON_BG)
        self.draw_button(screen, 'skip', 'Skip', color=BUTTON_BG)
        
        # Draw help text
        help_text = "Press 'S' for Scout, 'K' for Skip, or ESC to cancel"
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        help_rect = help_surface.get_rect(center=(self.x + self.width // 2, self.y + self.height - 20))
        screen.blit(help_surface, help_rect)
    
    def _create_buttons(self):
        # Position buttons relative to dialog
        self.buttons.clear(); self.button_states.clear()
        start_x = (self.width - (2 * 120 + 20)) // 2
        y = self.height - 70
        self.add_button('scout', start_x, y, 120, 40, enabled=self.can_scout())
        self.add_button('skip', start_x + 140, y, 120, 40, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == 'scout' and self.can_scout():
            cb = self.callback
            self.hide()
            if cb:
                cb('scout')
            return True
        if button_name == 'skip':
            cb = self.callback
            self.hide()
            if cb:
                cb('skip')
            return True
        return False