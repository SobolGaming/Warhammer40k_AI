"""
Dialog for handling unit coherency violations after movement.

When a unit's models are not in coherency after movement, this dialog allows
the player to choose which models to remove from play until coherency is restored.
"""

import pygame
from typing import List, Callable, Optional
from .base_dialog import BaseDialog, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_WARNING, TEXT_ERROR, BUTTON_BG, BUTTON_HOVER, BUTTON_SELECTED
from ..ui_fonts import get_ui_font
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.model import Model
import logging
logger = logging.getLogger(__name__)


class CoherencyViolationDialog(BaseDialog):
    """Dialog for handling unit coherency violations"""
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=600, height=500, draggable=True)
        
        # Dialog-specific state
        self.unit = None
        self.non_coherent_models = []
        self.models_to_remove = []
        self.removed_model_ids = []
        self.callback = None
        self.decision_request = None
        self._option_entries: List[dict] = []
        
        # UI elements
        self.model_buttons = []
        self.font_large = get_ui_font(28, bold=True)
        self.font_medium = get_ui_font(24, bold=True)
        self.font_small = get_ui_font(20, bold=False)
        
    def show(self, unit: Unit, non_coherent_models: List[int], callback: Callable[[str, List[str]], None], existing_dialogs: List = None, *, decision_request=None):
        """
        Show the coherency violation dialog.

        Args:
            unit: The unit with coherency violations
            non_coherent_models: List of model indices that are not coherent (for reference only)
            callback: Function to call when dialog is complete (bool indicates if models were removed)
            existing_dialogs: List of other visible dialogs to avoid overlapping with
        """
        # Position dialog to avoid overlap with existing dialogs
        if existing_dialogs:
            self.x, self.y = self.find_non_overlapping_position(existing_dialogs)

        super().show(callback)

        self.unit = unit
        self.non_coherent_models = non_coherent_models.copy()  # Keep for reference but don't restrict selection
        self.models_to_remove = []
        self.removed_model_ids = []
        self.callback = callback
        self.decision_request = decision_request
        self._option_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)

        self._create_model_buttons()
        self._create_dialog_buttons()

        # Update button positions in case dialog position was changed by overlap avoidance
        self._update_model_buttons()

        logger.info(f"INFO: Coherency violation dialog opened for {unit.name}")
        logger.info(f"INFO: Unit has coherency violations - select models to remove")
        
    def hide(self):
        """Hide the dialog"""
        super().hide()
        
        # Clean up dialog-specific state
        self.unit = None
        self.non_coherent_models = []
        self.models_to_remove = []
        self.removed_model_ids = []
        self.model_buttons = []
        self.decision_request = None
        self._option_entries = []
        
    def _create_model_buttons(self):
        """Create buttons for each model in the unit"""
        self.model_buttons = []

        if not self.unit:
            return

        button_width = 250
        button_height = 40

        # Show ALL alive models in the unit, not just non-coherent ones
        alive_models = [(i, model) for i, model in enumerate(self.unit.models) if model.is_alive]

        for i, (model_index, model) in enumerate(alive_models):
            # Store relative positions so they can be updated when dialog moves
            relative_x = 20
            relative_y = self.title_bar_height + 70 + i * (button_height + 10)

            button_rect = pygame.Rect(
                self.x + relative_x,
                self.y + relative_y,
                button_width,
                button_height
            )

            self.model_buttons.append({
                'rect': button_rect,
                'relative_x': relative_x,
                'relative_y': relative_y,
                'width': button_width,
                'height': button_height,
                'model_index': model_index,
                'model': model,
                'selected': False
            })

    def _update_model_buttons(self):
        """Update model button positions when dialog is moved"""
        for button in self.model_buttons:
            button['rect'] = pygame.Rect(
                self.x + button['relative_x'],
                self.y + button['relative_y'],
                button['width'],
                button['height']
            )

    def _create_dialog_buttons(self):
        """Create dialog control buttons"""
        # Position buttons at the bottom of the dialog
        button_y = self.y + self.height - 70  # Moved up 10 pixels

        self.buttons = {
            'remove_selected': pygame.Rect(self.x + 300, button_y, 140, 40)
            # Removed "Cancel" button - coherency issue must be resolved
        }

        # Initialize button states with proper positioning info
        self.button_states = {
            'remove_selected': {
                'hovered': False, 'pressed': False, 'enabled': True, 'state': 'normal',
                'relative_x': 300, 'relative_y': self.height - 70, 'width': 140, 'height': 40
            }
            # Removed "cancel" button state - coherency issue must be resolved
        }
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events for the dialog"""
        if not self.visible:
            return False
            
        # ESC key handling removed - coherency issue must be resolved
            
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
            # Removed cancel button handling - coherency issue must be resolved
        
        # Let base class handle other events (dragging, ESC, etc.)
        result = super().handle_event(event)

        # Update model button positions if dialog was dragged
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_model_buttons()

        return result

    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button click events. Return True if handled."""
        if button_name == 'remove_selected':
            self._remove_selected_models()
            return True
        # Removed cancel button handling - coherency issue must be resolved
        return False

    def _remove_selected_models(self):
        """Remove the selected models from play and re-check coherency"""
        selected_models = [btn['model_index'] for btn in self.model_buttons if btn['selected']]

        if not selected_models:
            logger.error("ERROR: No models selected for removal")
            return

        # Remove selected models
        removed_ids = []
        for model_index in sorted(selected_models, reverse=True):
            if model_index < len(self.unit.models):
                model = self.unit.models[model_index]
                logger.info(f"INFO: Removing {model.name} from play due to coherency violation")
                # Set wounds to 0 to make the model dead (is_alive property checks wounds > 0)
                model.wounds = 0
                # Call die() method to properly remove the model from the unit
                model.die()
                try:
                    removed_ids.append(model._id)
                except Exception:
                    pass
        self.removed_model_ids = removed_ids

        # Re-run coherency validation to see if the issue is resolved
        self._recheck_coherency_after_removal()
    

    
    def _cancel_removal(self):
        """Cancel the removal process (this shouldn't be allowed in actual rules)"""
        logger.info("INFO: Coherency violation removal cancelled")
        if self.callback:
            self.callback(False)
        self.hide()
    
    def _recheck_coherency_after_removal(self):
        """Re-check coherency after model removal and update dialog accordingly"""
        from ...utility.calcs import validate_unit_coherency_after_movement

        # Get current positions of all alive models
        final_positions = []
        for model in self.unit.models:
            if model.is_alive:
                final_positions.append(model.get_location())

        # Check coherency
        is_coherent, remaining_non_coherent = validate_unit_coherency_after_movement(self.unit, final_positions)

        if is_coherent:
            logger.info(f"INFO: {self.unit.name} is now in coherency")
            self._complete_removal()
        else:
            logger.warning(f"WARN: {self.unit.name} still has coherency violations")
            logger.info(f"INFO: Additional models may need to be removed")
            # Update the non_coherent_models for reference, but still show all models
            self.non_coherent_models = remaining_non_coherent
            # Recreate model buttons to reflect the current state (some models may have been removed)
            self._create_model_buttons()
            self._update_model_buttons()
    
    def _complete_removal(self):
        """Complete the model removal process"""
        # Unit position is now determined by model positions
        
        # Check if unit is still alive
        if not self.unit.is_alive():
            logger.info(f"INFO: {self.unit.name} has been destroyed due to coherency violations")
        else:
            logger.info(f"INFO: {self.unit.name} coherency violations resolved")
        
        if self.callback:
            option_id = self._option_entries[0]["option_id"] if self._option_entries else ""
            self.callback(option_id, list(self.removed_model_ids or []))
        self.hide()
    
    def draw(self, screen: pygame.Surface):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            return

        # Draw dialog background and title bar
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, f"Coherency Violation - {self.unit.name}")
        
        # Draw explanation (title is now in the title bar)
        explanation_lines = [
            "Unit has coherency violations. Select models to remove:",
            f"(Choose any models strategically - {len([m for m in self.unit.models if m.is_alive])} models available)"
        ]

        content_start_y = self.y + self.title_bar_height + 20  # Start below title bar
        for i, line in enumerate(explanation_lines):
            text_surface = self.font_medium.render(line, True, TEXT_WARNING)
            screen.blit(text_surface, (self.x + 20, content_start_y + i * 25))
        
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
        # Removed cancel button drawing - coherency issue must be resolved

        # Draw instructions
        instruction_text = "Select models to remove, then click 'Remove Selected'. Coherency will be re-checked."
        instruction_surface = self.font_small.render(instruction_text, True, TEXT_SECONDARY)
        screen.blit(instruction_surface, (self.x + 20, self.y + self.height - 30))
