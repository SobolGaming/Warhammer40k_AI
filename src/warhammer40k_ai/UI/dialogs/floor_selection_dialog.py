"""
Floor Selection Dialog for RUINS terrain movement.
Allows players to choose which floor level to target when moving units that can access upper floors.
"""

import pygame
from typing import Optional, Tuple, List
from .base_dialog import BaseDialog


class FloorSelectionDialog(BaseDialog):
    """Dialog for selecting target floor level in RUINS terrain."""
    
    def __init__(self, available_floors: List[int], unit_name: str = "Unit"):
        """
        Initialize floor selection dialog.
        
        Args:
            available_floors: List of floor levels available (e.g., [0, 1, 2])
            unit_name: Name of unit for display
        """
        super().__init__()
        self.available_floors = sorted(available_floors)
        self.unit_name = unit_name
        self.selected_floor = available_floors[0] if available_floors else 0
        
        # Dialog dimensions
        self.dialog_width = 400
        self.dialog_height = 200 + len(available_floors) * 40
        
        # Colors
        self.bg_color = (45, 45, 48)
        self.border_color = (63, 63, 70)
        self.text_color = (255, 255, 255)
        self.button_color = (60, 60, 67)
        self.button_hover_color = (75, 75, 82)
        self.button_selected_color = (0, 122, 204)
        
    def handle_event(self, event: pygame.event.Event) -> Optional[dict]:
        """Handle pygame events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return {"action": "cancel"}
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                return {"action": "confirm", "floor": self.selected_floor}
            elif event.key == pygame.K_UP:
                current_index = self.available_floors.index(self.selected_floor)
                if current_index > 0:
                    self.selected_floor = self.available_floors[current_index - 1]
            elif event.key == pygame.K_DOWN:
                current_index = self.available_floors.index(self.selected_floor)
                if current_index < len(self.available_floors) - 1:
                    self.selected_floor = self.available_floors[current_index + 1]
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                return self._handle_click(event.pos)
        
        return None
    
    def _handle_click(self, pos: Tuple[int, int]) -> Optional[dict]:
        """Handle mouse click events."""
        screen_width, screen_height = pygame.display.get_surface().get_size()
        dialog_x = (screen_width - self.dialog_width) // 2
        dialog_y = (screen_height - self.dialog_height) // 2
        
        x, y = pos
        
        # Check if click is within dialog bounds
        if not (dialog_x <= x <= dialog_x + self.dialog_width and 
                dialog_y <= y <= dialog_y + self.dialog_height):
            return {"action": "cancel"}
        
        # Convert to dialog-relative coordinates
        rel_x = x - dialog_x
        rel_y = y - dialog_y
        
        # Check floor selection buttons
        floor_buttons_start_y = 80
        for i, floor in enumerate(self.available_floors):
            button_y = floor_buttons_start_y + i * 40
            if (20 <= rel_x <= self.dialog_width - 20 and 
                button_y <= rel_y <= button_y + 30):
                self.selected_floor = floor
                return None
        
        # Check confirm/cancel buttons
        button_y = self.dialog_height - 50
        confirm_button_x = self.dialog_width // 2 - 80
        cancel_button_x = self.dialog_width // 2 + 10
        
        if (confirm_button_x <= rel_x <= confirm_button_x + 70 and 
            button_y <= rel_y <= button_y + 30):
            return {"action": "confirm", "floor": self.selected_floor}
        elif (cancel_button_x <= rel_x <= cancel_button_x + 70 and 
              button_y <= rel_y <= button_y + 30):
            return {"action": "cancel"}
        
        return None
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the floor selection dialog."""
        screen_width, screen_height = screen.get_size()
        dialog_x = (screen_width - self.dialog_width) // 2
        dialog_y = (screen_height - self.dialog_height) // 2
        
        # Draw dialog background
        dialog_rect = pygame.Rect(dialog_x, dialog_y, self.dialog_width, self.dialog_height)
        pygame.draw.rect(screen, self.bg_color, dialog_rect)
        pygame.draw.rect(screen, self.border_color, dialog_rect, 2)
        
        # Draw title
        font_large = pygame.font.Font(None, 24)
        title_text = font_large.render("Select Floor Level", True, self.text_color)
        title_rect = title_text.get_rect(center=(dialog_x + self.dialog_width // 2, dialog_y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw unit name
        font_medium = pygame.font.Font(None, 20)
        unit_text = font_medium.render(f"Moving: {self.unit_name}", True, self.text_color)
        unit_rect = unit_text.get_rect(center=(dialog_x + self.dialog_width // 2, dialog_y + 55))
        screen.blit(unit_text, unit_rect)
        
        # Draw floor selection buttons
        font_small = pygame.font.Font(None, 18)
        floor_buttons_start_y = dialog_y + 80
        
        for i, floor in enumerate(self.available_floors):
            button_y = floor_buttons_start_y + i * 40
            button_rect = pygame.Rect(dialog_x + 20, button_y, self.dialog_width - 40, 30)
            
            # Button color based on selection
            if floor == self.selected_floor:
                button_color = self.button_selected_color
            else:
                button_color = self.button_color
            
            pygame.draw.rect(screen, button_color, button_rect)
            pygame.draw.rect(screen, self.border_color, button_rect, 1)
            
            # Floor text
            if floor == 0:
                floor_text = "Ground Floor (Level 0)"
            else:
                floor_text = f"Floor Level {floor} ({floor * 4}\" elevation)"
            
            text_surface = font_small.render(floor_text, True, self.text_color)
            text_rect = text_surface.get_rect(center=button_rect.center)
            screen.blit(text_surface, text_rect)
        
        # Draw confirm/cancel buttons
        button_y = dialog_y + self.dialog_height - 50
        confirm_button_rect = pygame.Rect(dialog_x + self.dialog_width // 2 - 80, button_y, 70, 30)
        cancel_button_rect = pygame.Rect(dialog_x + self.dialog_width // 2 + 10, button_y, 70, 30)
        
        pygame.draw.rect(screen, self.button_color, confirm_button_rect)
        pygame.draw.rect(screen, self.button_color, cancel_button_rect)
        pygame.draw.rect(screen, self.border_color, confirm_button_rect, 1)
        pygame.draw.rect(screen, self.border_color, cancel_button_rect, 1)
        
        # Button text
        confirm_text = font_small.render("Confirm", True, self.text_color)
        cancel_text = font_small.render("Cancel", True, self.text_color)
        
        confirm_text_rect = confirm_text.get_rect(center=confirm_button_rect.center)
        cancel_text_rect = cancel_text.get_rect(center=cancel_button_rect.center)
        
        screen.blit(confirm_text, confirm_text_rect)
        screen.blit(cancel_text, cancel_text_rect)
        
        # Draw instructions
        instructions = [
            "Use UP/DOWN arrows or click to select floor",
            "Press ENTER to confirm, ESC to cancel"
        ]
        
        for i, instruction in enumerate(instructions):
            text = font_small.render(instruction, True, (180, 180, 180))
            text_rect = text.get_rect(center=(dialog_x + self.dialog_width // 2, 
                                            dialog_y + self.dialog_height - 100 + i * 15))
            screen.blit(text, text_rect)
