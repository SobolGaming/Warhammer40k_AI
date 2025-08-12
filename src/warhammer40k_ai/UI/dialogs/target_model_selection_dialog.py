import pygame
from typing import List, Callable, Optional, Dict
from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY
from ...classes.unit import Unit
from ...classes.model import Model

class TargetModelSelectionDialog(BaseDialog):
    """Dialog for selecting specific models to target in melee combat."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=600, height=500, draggable=True, center=True)

        # State
        self.attacking_unit: Optional[Unit] = None
        self.target_unit: Optional[Unit] = None
        self.weapon_declarations: List = []
        self.selection_type: str = ""  # "precision" or "wound_allocation"
        self.on_model_selected: Optional[Callable[[Model], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        # Button mapping: name -> Model
        self._button_to_model: Dict[str, Model] = {}

    def show(self, attacking_unit: Unit, target_unit: Unit, weapon_declarations: List,
             selection_type: str, on_model_selected: Callable[[Model], None],
             on_cancel: Optional[Callable[[], None]] = None) -> None:
        """
        Show the target model selection dialog.
        
        Args:
            attacking_unit: The unit making attacks
            target_unit: The unit being targeted
            weapon_declarations: List of weapon declarations
            selection_type: "precision" for precision targeting, "wound_allocation" for wound allocation
            on_model_selected: Callback when a model is selected
            on_cancel: Callback when cancelled
        """
        self.attacking_unit = attacking_unit
        self.target_unit = target_unit
        self.weapon_declarations = weapon_declarations
        self.selection_type = selection_type
        self.on_model_selected = on_model_selected
        self.on_cancel = on_cancel
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.attacking_unit = None
        self.target_unit = None
        self.weapon_declarations = []
        self.selection_type = ""
        self.on_model_selected = None
        self.on_cancel = None
        self._button_to_model.clear()

    def _create_buttons(self) -> None:
        # Clear any existing buttons
        self.buttons.clear()
        self.button_states.clear()
        self._button_to_model.clear()

        if not self.target_unit:
            return

        button_width = self.width - 40
        button_height = 80
        button_spacing = 10
        start_y = self.title_bar_height + 80  # Below title/instructions

        eligible_models = self._get_eligible_models()

        for i, model in enumerate(eligible_models):
            rel_x = 20
            rel_y = start_y + i * (button_height + button_spacing)
            name = f"model_{i}"
            self.add_button(name, rel_x, rel_y, button_width, button_height, enabled=True)
            self._button_to_model[name] = model

        # Cancel button (bottom-right)
        cancel_width, cancel_height = 120, 40
        rel_x = self.width - cancel_width - 20
        rel_y = self.height - cancel_height - 20
        self.add_button('cancel', rel_x, rel_y, cancel_width, cancel_height, enabled=True)

    def _get_eligible_models(self) -> List[Model]:
        """Get models that can be targeted based on selection type."""
        if not self.target_unit:
            return []

        if self.selection_type == "precision":
            # PRECISION weapons can target CHARACTER models
            character_models = []
            for model in self.target_unit.models:
                if not model.is_alive:
                    continue
                # Check if model has CHARACTER keyword
                keywords = getattr(model, 'keywords', []) or []
                if 'CHARACTER' in [kw.upper() for kw in keywords]:
                    character_models.append(model)
            return character_models
        elif self.selection_type == "wound_allocation":
            # For wound allocation, prioritize wounded models, then any alive model
            wounded_models = [model for model in self.target_unit.models 
                            if model.is_alive and model.wounds < model._base_wounds]
            if wounded_models:
                return wounded_models
            else:
                return [model for model in self.target_unit.models if model.is_alive]
        else:
            # Default: all alive models
            return [model for model in self.target_unit.models if model.is_alive]

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == 'cancel':
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name in self._button_to_model:
            model = self._button_to_model[button_name]
            if self.on_model_selected:
                self.on_model_selected(model)
            self.hide()
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        # Overlay behind the dialog
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        # Dialog background and title bar
        self.draw_dialog_background(screen)
        
        title = "Select Target Model"
        if self.selection_type == "precision":
            title = "Precision Targeting - Select CHARACTER"
        elif self.selection_type == "wound_allocation":
            title = "Wound Allocation - Select Target Model"
        
        self.draw_title_bar(screen, title)

        # Instructions
        instruction = "Choose a model to target with your attacks."
        if self.selection_type == "precision":
            instruction = "PRECISION weapons can target CHARACTER models directly."
        elif self.selection_type == "wound_allocation":
            instruction = "Select which model receives the wounds. Wounded models must be selected first."
        
        self.draw_instructions(screen, instruction)

        # Draw model buttons
        for name, rect in self.buttons.items():
            if name == 'cancel':
                continue
            
            model = self._button_to_model.get(name)
            if not model:
                continue

            # Model name and info
            model_name = getattr(model, 'name', f"Model {model.id}")
            
            # Draw the button
            self.draw_button(screen, name, model_name, color=BUTTON_BG)

            # Model stats and status
            wounds_text = f"W: {model.wounds}/{model._base_wounds}"
            stats_text = f"T: {model.toughness} | Sv: {model.save}+ | {wounds_text}"
            
            # Color wounded models differently
            text_color = (255, 100, 100) if model.wounds < model._base_wounds else TEXT_SECONDARY
            
            stats_surface = self.font_small.render(stats_text, True, text_color)
            screen.blit(stats_surface, (rect.x + 12, rect.y + 25))

            # Keywords (if CHARACTER)
            keywords = getattr(model, 'keywords', []) or []
            if 'CHARACTER' in [kw.upper() for kw in keywords]:
                char_surface = self.font_small.render("[CHARACTER]", True, (255, 215, 0))  # Gold
                screen.blit(char_surface, (rect.x + 12, rect.y + 45))

        # Draw cancel button
        self.draw_button(screen, 'cancel', 'Cancel', color=BUTTON_BG)
