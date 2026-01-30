"""
Mission Selection Dialog for Chapter Approved 2025/2026
Displays approved combinations of Primary Mission, Deployment, and Terrain Layout
"""

import pygame
from typing import Optional, Tuple, Dict, List, Iterable
from .base_dialog import BaseDialog
from ..ui_fonts import get_ui_font
from ...utility.rng import resolve_rng


class MissionSelectionDialog(BaseDialog):
    """Dialog for selecting official Chapter Approved mission combinations."""
    
    def __init__(self, screen_width: int, screen_height: int, combinations: Optional[Iterable[Dict]] = None):
        # Calculate dialog dimensions first
        dialog_width = min(900, screen_width - 100)
        dialog_height = min(700, screen_height - 100)
        
        super().__init__(screen_width, screen_height, dialog_width, dialog_height)
        self.title = "Select Mission - Chapter Approved 2025/2026"
        
        # Store dialog dimensions for convenience
        self.dialog_width = dialog_width
        self.dialog_height = dialog_height
        
        self.combinations = list(combinations or [])
        self.decision_request = None
        self._option_entries: List[Dict] = []

        # Selection state
        self.selected_combination = None
        self.selected_layout = None
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # UI elements
        self.font_title = get_ui_font(28, bold=True)
        self.font_header = get_ui_font(22, bold=True)
        self.font_normal = get_ui_font(18, bold=False)
        self.font_small = get_ui_font(16, bold=False)
        
        # Colors
        self.color_bg = (30, 30, 40)
        self.color_header = (70, 70, 80)
        self.color_selected = (50, 120, 200)
        self.color_hover = (60, 60, 80)
        self.color_text = (220, 220, 220)
        self.color_text_secondary = (180, 180, 180)
        self.color_border = (100, 100, 120)
        
        # Layout settings
        self.row_height = 35
        self.header_height = 40
        self.layout_button_size = 30
        
        # Calculate scrollable area
        self.content_height = len(self.combinations) * self.row_height + self.header_height
        self.visible_height = self.dialog_height - 200  # Leave space for title and buttons
        self.max_scroll = max(0, self.content_height - self.visible_height)

    def show(self, *, decision_request=None) -> None:
        self.decision_request = decision_request
        self._option_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)
            self.combinations = []
            for entry in self._option_entries:
                combo = dict(entry.get("payload", {}) or {}).get("combination")
                if isinstance(combo, dict):
                    self.combinations.append(combo)
        self.selected_combination = None
        self.selected_layout = None
        self.scroll_offset = 0
        self.content_height = len(self.combinations) * self.row_height + self.header_height
        self.max_scroll = max(0, self.content_height - self.visible_height)
        super().show()
        
    def handle_event(self, event) -> Optional[Dict]:
        """Handle user input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return {"action": "cancel"}
            elif event.key == pygame.K_RETURN:
                if self.selected_combination is not None and self.selected_layout is not None:
                    option_id = ""
                    if 0 <= self.selected_combination < len(self._option_entries):
                        option_id = self._option_entries[self.selected_combination].get("option_id", "")
                    return {
                        "action": "confirm",
                        "combination": self.combinations[self.selected_combination],
                        "layout": self.selected_layout,
                        "option_id": option_id,
                    }
            elif event.key == pygame.K_r:  # 'R' key for random
                self.pick_random_mission()
            elif event.key == pygame.K_UP:
                self._scroll(-1)
            elif event.key == pygame.K_DOWN:
                self._scroll(1)
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                return self._handle_click(event.pos)
            elif event.button == 4:  # Mouse wheel up
                self._scroll(-3)
            elif event.button == 5:  # Mouse wheel down
                self._scroll(3)
                
        elif event.type == pygame.MOUSEMOTION:
            self._handle_hover(event.pos)
            
        return None
    
    def _scroll(self, delta: int):
        """Scroll the mission list."""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta * 20))
    
    def _handle_click(self, pos: Tuple[int, int]) -> Optional[Dict]:
        """Handle mouse clicks."""
        x, y = pos
        dialog_x = (self.screen_width - self.dialog_width) // 2
        dialog_y = (self.screen_height - self.dialog_height) // 2
        
        # Check if click is within dialog
        if not (dialog_x <= x <= dialog_x + self.dialog_width and 
                dialog_y <= y <= dialog_y + self.dialog_height):
            return {"action": "cancel"}
        
        # Check Cancel/Pick Random/Confirm buttons
        button_y = dialog_y + self.dialog_height - 60
        if button_y <= y <= button_y + 40:
            cancel_x = dialog_x + 20
            random_x = dialog_x + 120  # Position between Cancel and Confirm
            confirm_x = dialog_x + self.dialog_width - 120
            
            if cancel_x <= x <= cancel_x + 80:
                return {"action": "cancel"}
            elif random_x <= x <= random_x + 100:
                self.pick_random_mission()
                return None  # Don't close dialog, just update selection
            elif confirm_x <= x <= confirm_x + 100:
                if self.selected_combination is not None and self.selected_layout is not None:
                    option_id = ""
                    if 0 <= self.selected_combination < len(self._option_entries):
                        option_id = self._option_entries[self.selected_combination].get("option_id", "")
                    return {
                        "action": "confirm",
                        "combination": self.combinations[self.selected_combination],
                        "layout": self.selected_layout,
                        "option_id": option_id,
                    }
        
        # Check mission combination clicks
        content_y = dialog_y + 80
        list_y = y - content_y + self.scroll_offset
        
        if list_y >= self.header_height:
            row_index = (list_y - self.header_height) // self.row_height
            if 0 <= row_index < len(self.combinations):
                # Check if clicking on layout buttons
                # Account for dialog position + content area offset + layout buttons position
                content_area_x = dialog_x + 10  # Content area starts at dialog_x + 10
                layouts_x = content_area_x + 445  # Match drawing position from _draw_combinations
                if layouts_x <= x <= dialog_x + self.dialog_width - 20:
                    layout_index = (x - layouts_x) // (self.layout_button_size + 5)
                    combination = self.combinations[row_index]
                    if 0 <= layout_index < len(combination["layouts"]):
                        self.selected_combination = row_index
                        self.selected_layout = combination["layouts"][layout_index]
                else:
                    # Clicking on the combination itself
                    self.selected_combination = row_index
                    self.selected_layout = None
        
        return None
    
    def _handle_hover(self, pos: Tuple[int, int]):
        """Handle mouse hover for visual feedback."""
        # Could implement hover effects here if desired
        pass
    
    def pick_random_mission(self):
        """Randomly select a mission combination and terrain layout."""
        rng = resolve_rng()
        # Pick a random combination from A-T
        self.selected_combination = rng.randint(0, len(self.combinations) - 1)
        
        # Pick a random terrain layout from the available options
        combination = self.combinations[self.selected_combination]
        self.selected_layout = rng.choice(combination["layouts"])
        
        print(f"Randomly selected: {combination['id']} - {combination['primary']} / {combination['deployment']} / Layout {self.selected_layout}")
    
    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button click events. Return True if handled."""
        if button_name == "cancel":
            return True  # Signal dialog should close
        elif button_name == "confirm":
            if self.selected_combination is not None and self.selected_layout is not None:
                return True  # Signal dialog should close with confirmation
        elif button_name == "pick_random":
            self.pick_random_mission()
            return False  # Don't close dialog, just update selection
        return False
    
    def draw(self, screen: pygame.Surface):
        """Draw the mission selection dialog."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
        
        # Dialog background
        dialog_x = (self.screen_width - self.dialog_width) // 2
        dialog_y = (self.screen_height - self.dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, self.dialog_width, self.dialog_height)
        
        pygame.draw.rect(screen, self.color_bg, dialog_rect)
        pygame.draw.rect(screen, self.color_border, dialog_rect, 2)
        
        # Title
        title_surface = self.font_title.render(self.title, True, self.color_text)
        title_x = dialog_x + (self.dialog_width - title_surface.get_width()) // 2
        screen.blit(title_surface, (title_x, dialog_y + 20))
        
        # Instructions
        instruction_text = "Select a mission combination and terrain layout"
        instruction_surface = self.font_normal.render(instruction_text, True, self.color_text_secondary)
        instruction_x = dialog_x + (self.dialog_width - instruction_surface.get_width()) // 2
        screen.blit(instruction_surface, (instruction_x, dialog_y + 50))
        
        # Content area with scrolling
        content_rect = pygame.Rect(dialog_x + 10, dialog_y + 80, 
                                 self.dialog_width - 20, self.visible_height)
        pygame.draw.rect(screen, (20, 20, 30), content_rect)
        pygame.draw.rect(screen, self.color_border, content_rect, 1)
        
        # Create clipping surface for scrollable content
        content_surface = pygame.Surface((content_rect.width, self.content_height))
        content_surface.fill((20, 20, 30))
        
        # Draw table header
        self._draw_header(content_surface)
        
        # Draw mission combinations
        self._draw_combinations(content_surface)
        
        # Blit scrolled content
        source_rect = pygame.Rect(0, self.scroll_offset, content_rect.width, 
                                min(self.visible_height, self.content_height - self.scroll_offset))
        screen.blit(content_surface, content_rect.topleft, source_rect)
        
        # Draw scrollbar if needed
        if self.max_scroll > 0:
            self._draw_scrollbar(screen, content_rect)
        
        # Bottom buttons
        self._draw_buttons(screen, dialog_x, dialog_y)
    
    def _draw_header(self, surface: pygame.Surface):
        """Draw the table header."""
        y = 5
        
        # Column headers
        headers = [
            ("ID", 20, 30),
            ("Primary Mission", 50, 200),
            ("Deployment", 270, 150),
            ("Terrain Layouts", 440, 200)
        ]
        
        header_rect = pygame.Rect(0, y, surface.get_width(), self.header_height - 5)
        pygame.draw.rect(surface, self.color_header, header_rect)
        
        for text, x, width in headers:
            header_surface = self.font_header.render(text, True, self.color_text)
            surface.blit(header_surface, (x, y + 10))
    
    def _draw_combinations(self, surface: pygame.Surface):
        """Draw the mission combination rows."""
        y = self.header_height
        
        for i, combo in enumerate(self.combinations):
            row_rect = pygame.Rect(0, y, surface.get_width(), self.row_height)
            
            # Row background
            if i == self.selected_combination:
                pygame.draw.rect(surface, self.color_selected, row_rect)
            elif i % 2 == 0:
                pygame.draw.rect(surface, (25, 25, 35), row_rect)
            
            # Row border
            pygame.draw.line(surface, self.color_border, 
                           (0, y + self.row_height), (surface.get_width(), y + self.row_height))
            
            # Mission ID
            id_surface = self.font_normal.render(combo["id"], True, self.color_text)
            surface.blit(id_surface, (25, y + 8))
            
            # Primary Mission
            primary_surface = self.font_normal.render(combo["primary"], True, self.color_text)
            surface.blit(primary_surface, (55, y + 8))
            
            # Deployment
            deployment_surface = self.font_normal.render(combo["deployment"], True, self.color_text)
            surface.blit(deployment_surface, (275, y + 8))
            
            # Terrain Layout buttons
            layouts_x = 445
            for j, layout in enumerate(combo["layouts"]):
                button_x = layouts_x + j * (self.layout_button_size + 5)
                button_rect = pygame.Rect(button_x, y + 3, self.layout_button_size, self.layout_button_size - 6)
                
                # Button color based on selection
                if (i == self.selected_combination and 
                    self.selected_layout == layout):
                    button_color = (100, 200, 100)
                    text_color = (255, 255, 255)
                else:
                    button_color = (60, 60, 80)
                    text_color = self.color_text
                
                pygame.draw.rect(surface, button_color, button_rect)
                pygame.draw.rect(surface, self.color_border, button_rect, 1)
                
                # Layout number
                layout_surface = self.font_small.render(str(layout), True, text_color)
                text_x = button_x + (self.layout_button_size - layout_surface.get_width()) // 2
                text_y = y + 5
                surface.blit(layout_surface, (text_x, text_y))
            
            y += self.row_height
    
    def _draw_scrollbar(self, screen: pygame.Surface, content_rect: pygame.Rect):
        """Draw scrollbar if content is scrollable."""
        scrollbar_width = 15
        scrollbar_x = content_rect.right - scrollbar_width
        scrollbar_height = content_rect.height
        
        # Scrollbar background
        scrollbar_bg = pygame.Rect(scrollbar_x, content_rect.top, scrollbar_width, scrollbar_height)
        pygame.draw.rect(screen, (40, 40, 50), scrollbar_bg)
        
        # Scrollbar thumb
        thumb_height = max(20, int(scrollbar_height * self.visible_height / self.content_height))
        thumb_y = content_rect.top + int(self.scroll_offset * (scrollbar_height - thumb_height) / self.max_scroll)
        thumb_rect = pygame.Rect(scrollbar_x + 2, thumb_y, scrollbar_width - 4, thumb_height)
        pygame.draw.rect(screen, (80, 80, 100), thumb_rect)
    
    def _draw_buttons(self, screen: pygame.Surface, dialog_x: int, dialog_y: int):
        """Draw the Cancel, Pick Random, and Confirm buttons."""
        button_y = dialog_y + self.dialog_height - 60
        
        # Cancel button
        cancel_rect = pygame.Rect(dialog_x + 20, button_y, 80, 40)
        pygame.draw.rect(screen, (120, 60, 60), cancel_rect)
        pygame.draw.rect(screen, self.color_border, cancel_rect, 2)
        cancel_text = self.font_normal.render("Cancel", True, self.color_text)
        cancel_text_x = cancel_rect.centerx - cancel_text.get_width() // 2
        cancel_text_y = cancel_rect.centery - cancel_text.get_height() // 2
        screen.blit(cancel_text, (cancel_text_x, cancel_text_y))
        
        # Pick Random button
        random_rect = pygame.Rect(dialog_x + 120, button_y, 100, 40)
        pygame.draw.rect(screen, (80, 80, 120), random_rect)  # Purple color for random
        pygame.draw.rect(screen, self.color_border, random_rect, 2)
        random_text = self.font_normal.render("Pick Random", True, self.color_text)
        random_text_x = random_rect.centerx - random_text.get_width() // 2
        random_text_y = random_rect.centery - random_text.get_height() // 2
        screen.blit(random_text, (random_text_x, random_text_y))
        
        # Confirm button
        confirm_enabled = (self.selected_combination is not None and 
                         self.selected_layout is not None)
        confirm_color = (60, 120, 60) if confirm_enabled else (60, 60, 60)
        
        confirm_rect = pygame.Rect(dialog_x + self.dialog_width - 120, button_y, 100, 40)
        pygame.draw.rect(screen, confirm_color, confirm_rect)
        pygame.draw.rect(screen, self.color_border, confirm_rect, 2)
        confirm_text = self.font_normal.render("Confirm", True, self.color_text)
        confirm_text_x = confirm_rect.centerx - confirm_text.get_width() // 2
        confirm_text_y = confirm_rect.centery - confirm_text.get_height() // 2
        screen.blit(confirm_text, (confirm_text_x, confirm_text_y))
        
        # Selection status
        if self.selected_combination is not None:
            combo = self.combinations[self.selected_combination]
            status_text = f"Selected: {combo['id']} - {combo['primary']} / {combo['deployment']}"
            if self.selected_layout is not None:
                status_text += f" / Layout {self.selected_layout}"
            else:
                status_text += " (Choose terrain layout)"
                
            status_surface = self.font_small.render(status_text, True, self.color_text_secondary)
            status_x = dialog_x + 20
            status_y = button_y - 25
            screen.blit(status_surface, (status_x, status_y))
