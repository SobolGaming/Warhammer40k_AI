"""
Dialog for handling unit coherency violations after movement.

When a unit's models are not in coherency after movement, this dialog allows
the player to choose which models to remove from play until coherency is restored.
"""

import pygame
from typing import List, Callable, Optional
from .base_dialog import BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_WARNING, TEXT_ERROR, BUTTON_BG, BUTTON_HOVER, BUTTON_SELECTED
from ...classes.unit import Unit
from ...classes.model import Model


class CoherencyViolationDialog(BaseDialog):
    """Dialog for handling unit coherency violations"""
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=600, height=500, draggable=True)
        
        # Dialog-specific state
        self.unit = None
        self.non_coherent_models = []
        self.models_to_remove = []
        self.callback = None
        
        # UI elements
        self.model_buttons = []
        self.font_large = pygame.font.Font(None, 28)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
    def show(self, unit: Unit, non_coherent_models: List[int], callback: Callable[[bool], None]):
        """
        Show the coherency violation dialog.
        
        Args:
            unit: The unit with coherency violations
            non_coherent_models: List of model indices that are not coherent
            callback: Function to call when dialog is complete (bool indicates if models were removed)
        """
        super().show(callback)
        
        self.unit = unit
        self.non_coherent_models = non_coherent_models.copy()
        self.models_to_remove = []
        self.callback = callback
        
        self._create_model_buttons()
        self._create_dialog_buttons()
        
        print(f"⚠️  Coherency violation dialog opened for {unit.name}")
        print(f"⚠️  {len(non_coherent_models)} models are not in coherency and must be removed")
        
    def hide(self):
        """Hide the dialog"""
        super().hide()
        
        # Clean up dialog-specific state
        self.unit = None
        self.non_coherent_models = []
        self.models_to_remove = []
        self.model_buttons = []
        
    def _create_model_buttons(self):
        """Create buttons for each non-coherent model"""
        self.model_buttons = []
        
        if not self.unit or not self.non_coherent_models:
            return
        
        button_width = 250
        button_height = 40
        start_y = self.y + 120
        
        for i, model_index in enumerate(self.non_coherent_models):
            if model_index < len(self.unit.models):
                model = self.unit.models[model_index]
                button_rect = pygame.Rect(
                    self.x + 20,
                    start_y + i * (button_height + 10),
                    button_width,
                    button_height
                )
                
                self.model_buttons.append({
                    'rect': button_rect,
                    'model_index': model_index,
                    'model': model,
                    'selected': False
                })
    
    def _create_dialog_buttons(self):
        """Create dialog control buttons"""
        self.buttons = {
            'remove_selected': pygame.Rect(self.x + 300, self.y + self.height - 100, 120, 40),
            'auto_remove': pygame.Rect(self.x + 430, self.y + self.height - 100, 120, 40),
            'cancel': pygame.Rect(self.x + 300, self.y + self.height - 50, 120, 40)
        }
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events for the dialog"""
        if not self.visible:
            return False
            
        # Handle ESC key to cancel
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._cancel_removal()
            return True
            
        # Handle mouse clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            
            # Check model selection buttons
            for button in self.model_buttons:
                if button['rect'].collidepoint(mouse_pos):
                    button['selected'] = not button['selected']
                    return True
            
            # Check dialog control buttons
            if self.buttons['remove_selected'].collidepoint(mouse_pos):
                self._remove_selected_models()
                return True
            elif self.buttons['auto_remove'].collidepoint(mouse_pos):
                self._auto_remove_models()
                return True
            elif self.buttons['cancel'].collidepoint(mouse_pos):
                self._cancel_removal()
                return True
        
        return super().handle_event(event)
    
    def _remove_selected_models(self):
        """Remove the selected models from play"""
        selected_models = [btn['model_index'] for btn in self.model_buttons if btn['selected']]
        
        if not selected_models:
            print("⚠️  No models selected for removal")
            return
        
        # Remove selected models
        for model_index in sorted(selected_models, reverse=True):
            if model_index < len(self.unit.models):
                model = self.unit.models[model_index]
                print(f"💀 Removing {model.name} from play due to coherency violation")
                model.is_alive = False
                model.wounds_remaining = 0
        
        # Check if coherency is now satisfied
        self._check_coherency_and_complete()
    
    def _auto_remove_models(self):
        """Automatically remove all non-coherent models"""
        for model_index in sorted(self.non_coherent_models, reverse=True):
            if model_index < len(self.unit.models):
                model = self.unit.models[model_index]
                print(f"💀 Auto-removing {model.name} from play due to coherency violation")
                model.is_alive = False
                model.wounds_remaining = 0
        
        self._complete_removal()
    
    def _cancel_removal(self):
        """Cancel the removal process (this shouldn't be allowed in actual rules)"""
        print("❌ Coherency violation removal cancelled")
        if self.callback:
            self.callback(False)
        self.hide()
    
    def _check_coherency_and_complete(self):
        """Check if coherency is satisfied and complete if so"""
        from ...utility.calcs import validate_unit_coherency_after_movement
        
        # Get current positions of all alive models
        final_positions = []
        for model in self.unit.models:
            if model.is_alive:
                final_positions.append(model.get_location())
        
        # Check coherency
        is_coherent, remaining_non_coherent = validate_unit_coherency_after_movement(self.unit, final_positions)
        
        if is_coherent:
            print(f"✅ {self.unit.name} is now in coherency")
            self._complete_removal()
        else:
            print(f"⚠️  {self.unit.name} still has coherency violations")
            print(f"⚠️  {len(remaining_non_coherent)} models still need to be removed")
            # Update the dialog with remaining violations
            self.non_coherent_models = remaining_non_coherent
            self._create_model_buttons()
    
    def _complete_removal(self):
        """Complete the model removal process"""
        # Unit position is now determined by model positions
        
        # Check if unit is still alive
        if not self.unit.is_alive():
            print(f"💀 {self.unit.name} has been destroyed due to coherency violations")
        else:
            print(f"✅ {self.unit.name} coherency violations resolved")
        
        if self.callback:
            self.callback(True)
        self.hide()
    
    def draw(self, screen: pygame.Surface):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            return
        
        # Draw dialog background
        super().draw(screen)
        
        # Draw title
        title_text = f"Coherency Violation - {self.unit.name}"
        title_surface = self.font_large.render(title_text, True, TEXT_ERROR)
        title_rect = title_surface.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_surface, title_rect)
        
        # Draw explanation
        explanation_lines = [
            "The following models are not in unit coherency and must be removed:",
            f"({len(self.non_coherent_models)} models out of coherency)"
        ]
        
        for i, line in enumerate(explanation_lines):
            text_surface = self.font_medium.render(line, True, TEXT_WARNING)
            screen.blit(text_surface, (self.x + 20, self.y + 60 + i * 25))
        
        # Draw model selection buttons
        for button in self.model_buttons:
            model = button['model']
            rect = button['rect']
            selected = button['selected']
            
            # Button background
            color = BUTTON_SELECTED if selected else BUTTON_BG
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, TEXT_PRIMARY, rect, 2)
            
            # Model info
            model_text = f"#{button['model_index'] + 1}: {model.name}"
            if hasattr(model, 'wounds_remaining'):
                model_text += f" ({model.wounds_remaining}W)"
            
            text_surface = self.font_small.render(model_text, True, TEXT_PRIMARY)
            text_rect = text_surface.get_rect(center=rect.center)
            screen.blit(text_surface, text_rect)
            
            # Selection indicator
            if selected:
                pygame.draw.circle(screen, TEXT_ERROR, (rect.right - 15, rect.centery), 8)
                pygame.draw.circle(screen, TEXT_PRIMARY, (rect.right - 15, rect.centery), 8, 2)
        
        # Draw control buttons
        self.draw_button(screen, 'remove_selected', "Remove Selected")
        self.draw_button(screen, 'auto_remove', "Remove All")
        self.draw_button(screen, 'cancel', "Cancel")
        
        # Draw instructions
        instruction_text = "Select models to remove, then click 'Remove Selected'"
        instruction_surface = self.font_small.render(instruction_text, True, TEXT_SECONDARY)
        screen.blit(instruction_surface, (self.x + 20, self.y + self.height - 30))
