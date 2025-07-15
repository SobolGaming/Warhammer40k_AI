import pygame
from typing import List, Optional, Callable, Dict, Any

# Font sizes
FONT_MEDIUM = 16
FONT_SMALL = 14

# Enhanced Colors
PANEL_BG = (45, 45, 48)  # Dark background
PANEL_BORDER = (63, 63, 70)  # Subtle border
BUTTON_BG = (60, 60, 67)  # Button background
BUTTON_HOVER = (75, 75, 82)  # Button hover
BUTTON_SELECTED = (100, 150, 200)  # Selected model
BUTTON_DISABLED = (40, 40, 40)  # Disabled button
TEXT_PRIMARY = (255, 255, 255)  # Primary text
TEXT_SECONDARY = (200, 200, 200)  # Secondary text
TEXT_DISABLED = (100, 100, 100)  # Disabled text
TEXT_SUCCESS = (100, 255, 100)  # Success/completed text
TEXT_WARNING = (255, 200, 100)  # Warning text
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow for model highlighting


class IndividualModelMovementDialog:
    """Dialog for moving individual models within a unit during movement phases"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 600
        self.height = 400
        self.visible = False
        self.unit = None
        self.movement_type = None  # 'move', 'advance', 'fall_back', 'scout'
        self.callback = None
        self.game_map = None
        self.max_distance = 0.0
        
        # Model movement tracking
        self.model_movements = {}  # {model_index: {'path': [...], 'completed': bool}}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        
        # Dragging functionality
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
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
        
        # UI elements
        self.model_buttons = []
        self.complete_button_rect = None
        self.skip_button_rect = None
        self.title_bar_rect = None
        
    def show(self, unit, movement_type: str, callback: Callable, game_map, max_distance: float = None):
        """Show the dialog for the given unit and movement type"""
        self.unit = unit
        self.movement_type = movement_type
        self.callback = callback
        self.game_map = game_map
        self.max_distance = max_distance or unit.movement
        self.visible = True
        
        # Reset movement tracking
        self.model_movements = {}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        self.dragging = False
        
        # Initialize model buttons
        self._create_model_buttons()
        
        print(f"🎯 Individual model movement dialog opened for {unit.name} ({movement_type})")
        print(f"📍 Select a model, then click on the battlefield to move it")
        
    def hide(self):
        """Hide the dialog"""
        self.visible = False
        self.unit = None
        self.movement_type = None
        self.callback = None
        self.game_map = None
        self.model_movements = {}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        self.dragging = False
        
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
        
        start_x = self.x + 20
        start_y = self.y + 80
        
        for i, model in enumerate(self.unit.models):
            if not model.is_alive:
                continue
                
            row = i // models_per_row
            col = i % models_per_row
            
            button_x = start_x + col * (button_width + button_spacing)
            button_y = start_y + row * (button_height + button_spacing)
            
            button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            self.model_buttons.append({
                'rect': button_rect,
                'model_index': i,
                'model': model
            })
        
        # Create control buttons
        self.complete_button_rect = pygame.Rect(self.x + self.width - 180, self.y + self.height - 50, 80, 35)
        self.skip_button_rect = pygame.Rect(self.x + self.width - 90, self.y + self.height - 50, 80, 35)
        
        # Title bar for dragging
        self.title_bar_rect = pygame.Rect(self.x, self.y, self.width, 50)
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events for the dialog"""
        if not self.visible:
            return False
            
        # Handle ESC key to close dialog
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.hide()
            return True
        
        # Handle mouse events for dragging
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            mouse_pos = event.pos
            
            # Ensure button positions are up-to-date before checking clicks
            self._create_model_buttons()
            
            # Check if clicking on title bar to start dragging
            if self.title_bar_rect and self.title_bar_rect.collidepoint(mouse_pos):
                self.dragging = True
                self.drag_offset_x = mouse_pos[0] - self.x
                self.drag_offset_y = mouse_pos[1] - self.y
                return True
                
            # Check complete button
            if self.complete_button_rect and self.complete_button_rect.collidepoint(mouse_pos):
                self._complete_movement()
                return True
                
            # Check skip button
            if self.skip_button_rect and self.skip_button_rect.collidepoint(mouse_pos):
                self._skip_movement()
                return True
                
            # Check model buttons
            for button in self.model_buttons:
                if button['rect'].collidepoint(mouse_pos):
                    self._select_model(button['model_index'])
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
                self._create_model_buttons()
                return True
                
        return False
        
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
                
        # Reset selection
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        
        return success
        
    def _move_model(self, model_index: int, destination) -> bool:
        """Move a specific model to the destination"""
        if model_index >= len(self.unit.models):
            return False
            
        # Use the individual model movement pathfinding
        from ...utility.calcs import get_individual_model_movement_path
        
        path = get_individual_model_movement_path(
            self.unit, model_index, destination, self.game_map, self.max_distance
        )
        
        if not path:
            print(f"❌ No valid path found for {self.unit.models[model_index].name}")
            return False
            
        # Move the model along the path
        model = self.unit.models[model_index]
        final_position = path[-1]
        
        # Update model position
        model.set_location(final_position[0], final_position[1], final_position[2])
        
        # Store the movement path
        model.last_move_path = path
        
        # Update unit centroid
        self.unit.reset_position()
        
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
            
            # Remove non-coherent models
            for model_index in sorted(non_coherent_models, reverse=True):
                if model_index < len(self.unit.models):
                    model = self.unit.models[model_index]
                    print(f"💀 Removing {model.name} from play due to coherency violation")
                    model.is_alive = False
                    model.wounds_remaining = 0
                    
            # Update unit after model removal
            self.unit.reset_position()
            
            if not self.unit.is_alive():
                print(f"💀 {self.unit.name} has been destroyed due to coherency violations")
        
        # Complete the movement
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
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, PANEL_BG, dialog_rect)
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 2)
        
        # Draw title bar (draggable area)
        title_bar_rect = pygame.Rect(self.x, self.y, self.width, 50)
        pygame.draw.rect(screen, (55, 55, 58), title_bar_rect)
        pygame.draw.rect(screen, PANEL_BORDER, title_bar_rect, 1)
        
        # Draw title
        title_text = f"Individual Model Movement: {self.unit.name}"
        title_surface = self.font_medium.render(title_text, True, TEXT_PRIMARY)
        screen.blit(title_surface, (self.x + 20, self.y + 15))
        
        # Draw drag hint
        drag_hint = "[Drag to move]"
        drag_surface = self.font_small.render(drag_hint, True, TEXT_SECONDARY)
        screen.blit(drag_surface, (self.x + 20, self.y + 35))
        
        # Draw movement type and distance info
        info_text = f"{self.movement_type.title()} Movement (Max: {self.max_distance:.1f}\")"
        info_surface = self.font_small.render(info_text, True, TEXT_SECONDARY)
        screen.blit(info_surface, (self.x + 20, self.y + 60))
        
        # Draw model buttons
        for button in self.model_buttons:
            model_index = button['model_index']
            model = button['model']
            rect = button['rect']
            
            # Determine button state
            if model_index == self.selected_model_index:
                button_color = BUTTON_SELECTED
                text_color = TEXT_PRIMARY
            elif model_index in self.model_movements and self.model_movements[model_index]['completed']:
                button_color = (100, 150, 100)  # Green for completed
                text_color = TEXT_SUCCESS
            elif not model.is_alive:
                button_color = BUTTON_DISABLED
                text_color = TEXT_DISABLED
            else:
                button_color = BUTTON_BG
                text_color = TEXT_PRIMARY
                
            # Draw button
            pygame.draw.rect(screen, button_color, rect)
            pygame.draw.rect(screen, PANEL_BORDER, rect, 1)
            
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
            instruction_color = TEXT_SECONDARY
            
        instruction_surface = self.font_small.render(instruction_text, True, instruction_color)
        screen.blit(instruction_surface, (self.x + 20, self.y + self.height - 80))
        
        # Draw control buttons
        if self.complete_button_rect:
            pygame.draw.rect(screen, BUTTON_BG, self.complete_button_rect)
            pygame.draw.rect(screen, PANEL_BORDER, self.complete_button_rect, 1)
            complete_text = self.font_small.render("Complete", True, TEXT_PRIMARY)
            complete_rect = complete_text.get_rect(center=self.complete_button_rect.center)
            screen.blit(complete_text, complete_rect)
            
        if self.skip_button_rect:
            pygame.draw.rect(screen, BUTTON_BG, self.skip_button_rect)
            pygame.draw.rect(screen, PANEL_BORDER, self.skip_button_rect, 1)
            skip_text = self.font_small.render("Skip", True, TEXT_PRIMARY)
            skip_rect = skip_text.get_rect(center=self.skip_button_rect.center)
            screen.blit(skip_text, skip_rect) 