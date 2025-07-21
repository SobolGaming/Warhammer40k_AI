import pygame
from typing import List, Optional, Callable, Dict, Any
from .base_dialog import BaseDialog, TEXT_SUCCESS, TEXT_WARNING, BUTTON_SELECTED

# Additional colors specific to this dialog
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow for model highlighting


class IndividualModelMovementDialog(BaseDialog):
    """Dialog for moving individual models within a unit during movement phases"""
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=600, height=400, draggable=True)
        
        # Dialog-specific state
        self.unit = None
        self.movement_type = None  # 'move', 'advance', 'fall_back', 'scout', 'pile_in', 'consolidate', 'charge'
        self.game_map = None
        self.max_distance = 0.0
        
        # Model movement tracking
        self.model_movements = {}  # {model_index: {'path': [...], 'completed': bool}}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        
        # UI elements
        self.model_buttons = []
        
    def show(self, unit, movement_type: str, callback: Callable, game_map, max_distance: float = None):
        """Show the dialog for the given unit and movement type"""
        # Call parent show method
        super().show(callback)
        
        # Dialog-specific initialization
        self.unit = unit
        self.movement_type = movement_type
        self.game_map = game_map
        self.max_distance = max_distance or unit.movement
        
        # Reset movement tracking
        self.model_movements = {}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        
        # Initialize model buttons and dialog buttons
        self._create_model_buttons()
        self._create_dialog_buttons()
        
        print(f"🎯 Individual model movement dialog opened for {unit.name} ({movement_type})")
        print(f"📍 Select a model, then click on the battlefield to move it")
        
    def hide(self):
        """Hide the dialog"""
        super().hide()
        
        # Clean up dialog-specific state
        self.unit = None
        self.movement_type = None
        self.game_map = None
        self.model_movements = {}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        
    def _create_model_buttons(self):
        """Create buttons for each model in the unit"""
        self.model_buttons = []
        
        if not self.unit or not self.unit.models:
            return
            
        # Calculate button layout
        button_width = 180
        button_height = 30
        button_spacing = 5
        models_per_row = 3
        
        start_x = 20  # Relative to dialog
        start_y = 80  # Relative to dialog
        
        for i, model in enumerate(self.unit.models):
            if not model.is_alive:
                continue
                
            row = i // models_per_row
            col = i % models_per_row
            
            button_x = start_x + col * (button_width + button_spacing)
            button_y = start_y + row * (button_height + button_spacing)
            
            # Store relative position for re-positioning during drag
            self.model_buttons.append({
                'rect': pygame.Rect(self.x + button_x, self.y + button_y, button_width, button_height),
                'model_index': i,
                'model': model,
                'relative_x': button_x,
                'relative_y': button_y,
                'width': button_width,
                'height': button_height
            })
    
    def _create_dialog_buttons(self):
        """Create the Complete and Skip buttons using base dialog button system"""
        # Add Complete button
        self.add_button('complete', self.width - 180, self.height - 50, 80, 35)
        
        # Add Skip button  
        self.add_button('skip', self.width - 90, self.height - 50, 80, 35)
        
    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button click events from base class"""
        if button_name == 'complete':
            self._complete_movement()
            return True
        elif button_name == 'skip':
            self._skip_movement()
            return True
        return False
    
    def _handle_dialog_click(self, mouse_pos) -> bool:
        """Handle clicks within dialog area"""
        # Update model button positions
        self._update_model_buttons()
        
        # Check model buttons
        for button in self.model_buttons:
            if button['rect'].collidepoint(mouse_pos):
                self._select_model(button['model_index'])
                return True
        return False
    
    def _update_model_buttons(self):
        """Update model button positions when dialog is moved"""
        for button in self.model_buttons:
            button['rect'].x = self.x + button['relative_x']
            button['rect'].y = self.y + button['relative_y']
    
    def _update_buttons(self):
        """Override base class method to also update model buttons"""
        super()._update_buttons()
        self._update_model_buttons()
        
    def _select_model(self, model_index: int):
        """Select a model for movement"""
        if model_index >= len(self.unit.models):
            return
            
        model = self.unit.models[model_index]
        
        # Check if model is already moved
        if model_index in self.model_movements and self.model_movements[model_index]['completed']:
            print(f"⚠️  {model.name} has already been moved")
            return
            
        self.selected_model_index = model_index
        self.awaiting_battlefield_click = True
        
        print(f"🎯 Selected {model.name} (Model #{model_index + 1}) for {self.movement_type} movement")
        print(f"📍 Click on the battlefield to move this model")
        
    def get_highlighted_model_index(self) -> Optional[int]:
        """Get the index of the currently highlighted model for battlefield rendering"""
        return self.selected_model_index
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle pygame events for the dialog.
        Override base class to handle battlefield clicks specially.
        """
        if not self.visible:
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

        # Handle coherency dialog events first if it's open
        if hasattr(self, 'coherency_dialog') and self.coherency_dialog.visible:
            print(f"🔍 DEBUG: {dialog_name} - Delegating to coherency dialog")
            return self.coherency_dialog.handle_event(event)

        # Handle ESC key to close dialog
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            print(f"🔍 DEBUG: {dialog_name} - ESC key pressed, hiding dialog")
            self.hide()
            return True
        
        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            mouse_pos = event.pos
            
            # Ensure button positions are up-to-date
            self._update_buttons()
            
            # Check if clicking on title bar to start dragging
            if self.draggable and self.title_bar_rect and self.title_bar_rect.collidepoint(mouse_pos):
                self.dragging = True
                self.drag_offset_x = mouse_pos[0] - self.x
                self.drag_offset_y = mouse_pos[1] - self.y
                return True
            
            # Check button clicks
            for button_name, button_rect in self.buttons.items():
                if button_rect.collidepoint(mouse_pos):
                    if self._handle_button_click(button_name):
                        return True
            
            # Check if click is within dialog bounds
            dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
            if dialog_rect.collidepoint(mouse_pos):
                # Let subclass handle the click
                if self._handle_dialog_click(mouse_pos):
                    return True
            else:
                # Click outside dialog - special handling for battlefield clicks
                if self.awaiting_battlefield_click:
                    # Don't close dialog, let the parent handler process the battlefield click
                    return False
                else:
                    # Click outside dialog without a model selected - show helpful message
                    print(f"⚠️  Please select a model first, then click on the battlefield to move it")
                    print(f"📍 Or press ESC to close the dialog")
                    # Don't close dialog, let user try again
                    return True
                
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:  # Left click release
            if self.dragging:
                self.dragging = False
                return True
                
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                # Update dialog position
                self.x = event.pos[0] - self.drag_offset_x
                self.y = event.pos[1] - self.drag_offset_y

                # Keep dialog within screen bounds
                self.x = max(0, min(self.screen_width - self.width, self.x))
                self.y = max(0, min(self.screen_height - self.height, self.y))

                # Update button positions
                self._update_title_bar()
                self._update_buttons()
                return True
            else:
                # Only consume mouse motion events if the mouse is over the dialog
                # This allows the phase handler to handle battlefield mouse motion for path preview
                mouse_pos = event.pos
                dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)

                if dialog_rect.collidepoint(mouse_pos):
                    # Mouse is over the dialog - update hover state and consume the event
                    self._update_hover(event.pos)
                    return True
                else:
                    # Mouse is outside dialog (likely over battlefield) - don't consume the event
                    # This allows the phase handler to handle it for path preview
                    return False
        
        # Let subclass handle other events
        return self._handle_other_events(event)
    
    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        """Handle other events not processed by the main event handler"""
        return False
    
    def _update_hover(self, mouse_pos):
        """Update hover state for buttons"""
        self.hovered_button = None
        for button_name, button_rect in self.buttons.items():
            if button_rect.collidepoint(mouse_pos):
                self.hovered_button = button_name
                break
        
    def handle_battlefield_click(self, battlefield_x: float, battlefield_y: float, battlefield_z: float) -> bool:
        """Handle battlefield click for model movement"""
        if not self.awaiting_battlefield_click or self.selected_model_index is None:
            return False
            
        destination = (battlefield_x, battlefield_y, battlefield_z)
        
        # Attempt to move the selected model
        success = self._move_model(self.selected_model_index, destination)
        
        if success:
            # Mark model as moved
            self.model_movements[self.selected_model_index] = {
                'path': [],  # Path would be stored here if needed
                'completed': True
            }
            
            # Check if all models are moved
            if self._all_models_moved():
                print(f"✅ All models in {self.unit.name} have been moved")
                # Auto-complete after short delay or continue allowing more moves
                
            # Reset selection only on successful movement
            self.selected_model_index = None
            self.awaiting_battlefield_click = False
        else:
            # On failure, keep the model selected and continue waiting for battlefield clicks
            print(f"❌ Movement failed for {self.unit.models[self.selected_model_index].name}")
            print(f"🔄 Model remains selected. Try clicking on a valid location.")
        
        return success
        
    def _move_model(self, model_index: int, destination) -> bool:
        """Move a specific model to the destination"""
        if model_index >= len(self.unit.models):
            print(f"❌ Invalid model index: {model_index}")
            return False
            
        model = self.unit.models[model_index]
        
        # Use the individual model movement pathfinding
        from ...utility.calcs import get_individual_model_movement_path
        from ...classes.unit import MovementAction

        # Map movement type string to MovementAction enum
        movement_action_map = {
            'move': MovementAction.MOVE,
            'advance': MovementAction.ADVANCE,
            'fall_back': MovementAction.FALL_BACK,
            'charge': MovementAction.CHARGE,
            'scout': MovementAction.MOVE,  # Scout uses normal movement rules
            'pile_in': MovementAction.MOVE,  # Pile-in uses normal movement rules
            'consolidate': MovementAction.MOVE  # Consolidate uses normal movement rules
        }

        movement_action = movement_action_map.get(self.movement_type, MovementAction.MOVE)

        # Use movement-specific pathfinding based on movement type
        if movement_action == MovementAction.CHARGE:
            # Use charge-specific pathfinding that allows engagement range
            from ...utility.calcs import get_charge_movement_path
            path_result = get_charge_movement_path(
                model, destination[:2], self.max_distance, self.game_map
            )
        else:
            # Use standard pathfinding for other movement types
            from ...utility.calcs import get_movement_path_preview
            path_result = get_movement_path_preview(
                model, destination[:2], self.max_distance, self.game_map
            )

        print(f"🔍 DEBUG: Pathfinding result for {model.name} to {destination}")
        print(f"🔍 DEBUG: Path valid: {path_result['valid']}, movement_action: {movement_action}")
        print(f"🔍 DEBUG: Reason: {path_result['reason']}")
        if path_result['path']:
            print(f"🔍 DEBUG: Path length: {len(path_result['path'])}")

        if not path_result['valid'] or not path_result['path']:
            print(f"❌ No valid path found for {model.name} (Model #{model_index + 1})")
            print(f"   Reason: {path_result['reason']}")
            print(f"   Try clicking closer or on a clear area")
            return False

        # Convert 2D path back to 3D for movement
        path_3d = [(p[0], p[1], destination[2]) for p in path_result['path']]

        # Move the model along the path
        final_position = path_3d[-1]
        
        # Update model position (preserve current facing)
        current_facing = model.model_base.facing if hasattr(model.model_base, 'facing') else 0.0
        model.set_location(final_position[0], final_position[1], final_position[2], current_facing)
        
        # Store the movement path
        model.last_move_path = path_3d
        
        # Unit position is now determined by model positions
        
        print(f"✅ {model.name} (Model #{model_index + 1}) moved to ({final_position[0]:.1f}, {final_position[1]:.1f})")
        return True
        
    def _all_models_moved(self) -> bool:
        """Check if all models have been moved"""
        for i, model in enumerate(self.unit.models):
            if not model.is_alive:
                continue
            if i not in self.model_movements or not self.model_movements[i]['completed']:
                return False
        return True
        
    def _complete_movement(self):
        """Complete the movement phase and validate coherency"""
        if not self.unit:
            return

        # Validate unit coherency
        from ...utility.calcs import validate_unit_coherency_after_movement

        # Get final positions of all models
        final_positions = []
        for model in self.unit.models:
            final_positions.append(model.get_location())

        is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self.unit, final_positions)

        if not is_coherent:
            print(f"⚠️  {self.unit.name} coherency violation!")
            print(f"⚠️  Models {non_coherent_models} are not coherent and must be removed from play")

            # Show coherency violation dialog for user to choose which models to remove
            self._show_coherency_violation_dialog(non_coherent_models)
        else:
            # No coherency violations, complete normally
            self._finalize_movement_completion()

    def _show_coherency_violation_dialog(self, non_coherent_models: list):
        """Show the coherency violation dialog"""
        from .coherency_violation_dialog import CoherencyViolationDialog

        # Create and show the coherency dialog
        coherency_dialog = CoherencyViolationDialog(self.screen_width, self.screen_height)

        # Collect all visible dialogs to avoid overlap
        existing_dialogs = []
        if self.visible:
            existing_dialogs.append(self)

        # Check for other potentially visible dialogs in the game UI
        # This helps avoid overlap with scout dialogs, movement dialogs, etc.
        try:
            # Try to access the game UI to check for other visible dialogs
            from ...UI.game_ui import HumanUIInterface
            # Note: This is a best-effort approach - we'll collect what we can
            print(f"🔍 DEBUG: Collecting existing dialogs to avoid overlap with coherency dialog")
        except:
            pass  # If we can't access other dialogs, just use what we have

        coherency_dialog.show(self.unit, non_coherent_models, self._on_coherency_resolution, existing_dialogs)

        # Store reference to the dialog so it can be drawn and handled
        self.coherency_dialog = coherency_dialog

    def _on_coherency_resolution(self, models_removed: bool):
        """Called when coherency violation dialog is complete"""
        if models_removed:
            print(f"✅ Coherency violations resolved for {self.unit.name}")
        else:
            print(f"❌ Coherency resolution cancelled for {self.unit.name}")

        # Clean up dialog reference
        if hasattr(self, 'coherency_dialog'):
            delattr(self, 'coherency_dialog')

        # Complete the movement
        self._finalize_movement_completion()

    def _finalize_movement_completion(self):
        """Finalize the movement completion"""
        print(f"✅ {self.unit.name} {self.movement_type} movement completed")

        # Call callback with completion status
        if self.callback:
            self.callback(True)  # Movement completed

        self.hide()
        
    def _skip_movement(self):
        """Skip movement for this unit"""
        print(f"⏭️  Skipping {self.movement_type} movement for {self.unit.name}")

        # Call callback with skip status
        if self.callback:
            self.callback(False)  # Movement skipped

        self.hide()
        
    def draw(self, screen: pygame.Surface):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            return
            
        # Draw dialog background
        self.draw_dialog_background(screen)
        
        # Draw title bar
        title = f"Individual Model Movement: {self.unit.name}"
        subtitle = f"{self.movement_type.title()} Movement (Max: {self.max_distance:.1f}\")"
        self.draw_title_bar(screen, title, subtitle)
        
        # Draw model buttons
        self._update_model_buttons()
        for button in self.model_buttons:
            model_index = button['model_index']
            model = button['model']
            rect = button['rect']
            
            # Determine button state
            if model_index == self.selected_model_index:
                button_color = BUTTON_SELECTED
                text_color = (255, 255, 255)  # TEXT_PRIMARY
            elif model_index in self.model_movements and self.model_movements[model_index]['completed']:
                button_color = (100, 150, 100)  # Green for completed
                text_color = TEXT_SUCCESS
            elif not model.is_alive:
                button_color = (40, 40, 40)  # BUTTON_DISABLED
                text_color = (100, 100, 100)  # TEXT_DISABLED
            else:
                button_color = (60, 60, 67)  # BUTTON_BG
                text_color = (255, 255, 255)  # TEXT_PRIMARY
                
            # Draw button
            pygame.draw.rect(screen, button_color, rect)
            pygame.draw.rect(screen, (63, 63, 70), rect, 1)  # PANEL_BORDER
            
            # Draw model name with number and status
            model_name = f"#{model_index + 1}: {model.name}"
            if model_index in self.model_movements and self.model_movements[model_index]['completed']:
                model_name += " ✓"
            elif not model.is_alive:
                model_name += " (Dead)"
                
            text_surface = self.font_small.render(model_name, True, text_color)
            text_rect = text_surface.get_rect(center=rect.center)
            screen.blit(text_surface, text_rect)
            
        # Draw instructions
        if self.awaiting_battlefield_click:
            instruction_text = f"Click on battlefield to move #{self.selected_model_index + 1}: {self.unit.models[self.selected_model_index].name}"
            instruction_color = TEXT_WARNING
        else:
            instruction_text = "Select a model, then click on battlefield to move it. ESC to close."
            instruction_color = (200, 200, 200)  # TEXT_SECONDARY
            
        instruction_surface = self.font_small.render(instruction_text, True, instruction_color)
        screen.blit(instruction_surface, (self.x + 20, self.y + self.height - 80))
        
        # Draw control buttons using base class method
        self.draw_button(screen, 'complete', "Complete")
        self.draw_button(screen, 'skip', "Skip")

        # Draw coherency dialog if it's open
        if hasattr(self, 'coherency_dialog') and self.coherency_dialog.visible:
            self.coherency_dialog.draw(screen)