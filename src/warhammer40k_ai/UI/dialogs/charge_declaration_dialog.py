import pygame
from typing import List, Optional, Callable

# Font sizes
FONT_LARGE = 18
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
TEXT_ACCENT = (100, 149, 237)  # Blue accent color for keywords
VALID_TARGET_COLOR = (0, 200, 0)  # Green for valid targets
INVALID_TARGET_COLOR = (200, 0, 0)  # Red for invalid targets
WARNING_COLOR = (255, 165, 0)  # Orange for warnings


class ChargeDeclarationDialog:
    """Dialog for declaring charges during the charge phase"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 650  # Increased width
        self.height = 550  # Increased height
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        
        # Calculate position (center of screen)
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2
        
        # Fonts
        try:
            self.font_large = pygame.font.SysFont('Arial', FONT_LARGE, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', FONT_MEDIUM, bold=True)
            self.font_small = pygame.font.SysFont('Arial', FONT_SMALL, bold=False)
        except:
            self.font_large = pygame.font.Font(None, FONT_LARGE)
            self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
            self.font_small = pygame.font.Font(None, FONT_SMALL)
        
        # Available targets
        self.available_targets = []
        self.valid_targets = []
        self.invalid_targets = []
        
        # UI state
        self.scroll_offset = 0
        self.max_scroll = 0
        self.hovered_target = -1
        self.selected_target = None
        
        # Button rectangles - made wider
        button_width = 140  # Increased from 120
        button_height = 35
        button_spacing = 20  # Increased spacing
        
        start_x = self.x + (self.width - (2 * button_width + button_spacing)) // 2
        button_y = self.y + self.height - 50
        
        self.declare_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.cancel_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        
        self.hovered_button = None
    
    def show(self, unit, callback, game_map=None, game_view=None):
        """Show the charge declaration dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.game_view = game_view
        self.visible = True
        
        # Clear previous state
        self.selected_target = None
        self.scroll_offset = 0
        self.hovered_target = -1
        
        # Position dialog based on player
        if unit.get_parent_army() and unit.get_parent_army().player:
            player_name = unit.get_parent_army().player.name
            if "Player 1" in player_name or "1" in player_name:
                # Player 1 - position on left side of battlefield
                self.x = 50  # Small margin from left edge
            else:
                # Player 2 - position on right side of battlefield  
                self.x = self.screen_width - self.width - 50  # Small margin from right edge
        else:
            # Fallback to center if player info not available
            self.x = (self.screen_width - self.width) // 2
        
        # Center vertically
        self.y = (self.screen_height - self.height) // 2
        
        # Update button positions
        button_width = 140  # Increased width
        button_height = 35
        button_spacing = 20  # Increased spacing
        start_x = self.x + (self.width - (2 * button_width + button_spacing)) // 2
        button_y = self.y + self.height - 50
        
        self.declare_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.cancel_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        
        # Get available targets
        self._update_available_targets()
        
        # Calculate scroll limits
        target_count = len(self.available_targets)
        target_height = 60
        total_height = target_count * target_height
        visible_height = self.height - 240  # Account for header, unit info, and buttons (160 + 240 = 400)
        self.max_scroll = max(0, total_height - visible_height)
        
        print(f"⚔️ ChargeDeclarationDialog shown for {unit.name}")
        print(f"⚔️ Found {len(self.valid_targets)} valid targets")
        print(f"⚔️ Found {len(self.invalid_targets)} invalid targets")
        
        # Check if unit is eligible to charge
        if not self._is_unit_eligible_to_charge():
            print(f"❌ {unit.name} is not eligible to charge")
            self.hide()
            return
    
    def hide(self):
        """Hide the charge declaration dialog"""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        self.available_targets = []
        self.valid_targets = []
        self.invalid_targets = []
        self.selected_target = None
        self.scroll_offset = 0
        self.hovered_target = -1
    
    def _update_available_targets(self):
        """Update the list of available targets"""
        if not self.game_map or not self.unit:
            return
        
        # Get all enemy units
        enemy_units = self.game_map.get_enemy_units(self.unit)
        
        # Filter out dead units
        enemy_units = [unit for unit in enemy_units if unit.is_alive()]
        
        # Separate valid and invalid targets
        self.valid_targets = []
        self.invalid_targets = []
        
        for target in enemy_units:
            if self.unit.can_declare_charge_against(target, self.game_view.game):
                self.valid_targets.append(target)
            else:
                self.invalid_targets.append(target)
        
        # Combine for display
        self.available_targets = self.valid_targets + self.invalid_targets
        
        # Sort targets by distance (closest first)
        def get_distance_to_target(target):
            return self.game_map.get_distance_between_units(self.unit, target)
        
        self.valid_targets.sort(key=get_distance_to_target)
        self.available_targets = self.valid_targets + self.invalid_targets
    
    def _is_unit_eligible_to_charge(self) -> bool:
        """Check if the unit is eligible to declare a charge."""
        if not self.unit:
            print(f"❌ Charge eligibility check failed: No unit selected")
            return False

        # Check if unit has already charged this round
        if self.unit.round_state.declared_charge_this_round:
            print(f"❌ {self.unit.name} charge eligibility: Already declared charge this round")
            return False

        # Check if unit advanced this round (unless special abilities allow charging after advance)
        if self.unit.round_state.advanced_this_round:
            can_charge_after_advance = self.unit.can_charge_after_advance()
            print(f"🔍 {self.unit.name} advanced this round. Can charge after advance: {can_charge_after_advance}")
            if not can_charge_after_advance:
                print(f"❌ {self.unit.name} charge eligibility: Advanced this round and cannot charge after advancing")
                return False

        # Check if unit fell back this round (unless special abilities allow charging after fall back)
        if self.unit.round_state.fell_back_this_round:
            print(f"❌ {self.unit.name} charge eligibility: Fell back this round and cannot charge")
            # TODO: Check for special abilities that allow charging after fall back
            return False

        # Check if unit is already in engagement range
        if self.game_map:
            enemy_units = self.game_map.get_enemy_units(self.unit)
            is_engaged = any(self.game_map.is_within_engagement_range(self.unit, enemy)
                           for enemy in enemy_units if enemy.is_alive())
            if is_engaged:
                engaged_enemies = [enemy.name for enemy in enemy_units
                                 if enemy.is_alive() and self.game_map.is_within_engagement_range(self.unit, enemy)]
                print(f"❌ {self.unit.name} charge eligibility: Already in engagement range of {', '.join(engaged_enemies)}")
                return False

        print(f"✅ {self.unit.name} is eligible to charge")
        return True
    
    def _get_target_validation_info(self, target):
        """Get validation information for a target"""
        if not self.unit or not target:
            return {"valid": False, "reason": "Invalid target"}
        
        # Check if unit is alive
        if not target.is_alive():
            return {"valid": False, "reason": "Target is destroyed"}
        
        # Check if unit has already charged
        if self.unit.round_state.declared_charge_this_round:
            return {"valid": False, "reason": "Unit has already charged this round"}
        
        # Check if unit advanced this round
        if self.unit.round_state.advanced_this_round:
            if not self.unit.can_charge_after_advance():
                return {"valid": False, "reason": "Unit advanced and cannot charge"}
        
        # Check if unit fell back this round
        if self.unit.round_state.fell_back_this_round:
            return {"valid": False, "reason": "Unit fell back and cannot charge"}
        
        # Check if unit is already in engagement range
        if self.game_map.is_within_engagement_range(self.unit, target):
            return {"valid": False, "reason": "Unit is already in engagement range"}
        
        # Check distance
        distance = self.game_map.get_distance_between_units(self.unit, target)
        if distance > self.unit.max_charge_distance:
            return {"valid": False, "reason": f"Target too far ({distance:.1f}\" > {self.unit.max_charge_distance}\")"}
        
        # Check if path is blocked (simplified)
        if self.game_map.is_path_blocked(self.unit, target):
            return {"valid": False, "reason": "Path to target is blocked"}
        
        return {"valid": True, "reason": f"Distance: {distance:.1f}\""}
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        
        # Check if event is within dialog bounds
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        event_pos = getattr(event, 'pos', None)
        
        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Only handle clicks within dialog bounds
                if event_pos and dialog_rect.collidepoint(event_pos):
                    return self.handle_click(event_pos)
            elif event.button == 4:  # Scroll up
                if event_pos and dialog_rect.collidepoint(event_pos):
                    self.scroll_offset = max(0, self.scroll_offset - 30)
                    return True
            elif event.button == 5:  # Scroll down
                if event_pos and dialog_rect.collidepoint(event_pos):
                    self.scroll_offset = min(self.max_scroll, self.scroll_offset + 30)
                    return True
        elif event.type == pygame.MOUSEMOTION:
            # Only handle motion within dialog bounds
            if event_pos and dialog_rect.collidepoint(event_pos):
                self.update_hover(event_pos)
                return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            elif event.key == pygame.K_RETURN and self.selected_target:
                self._execute_charge()
                return True
        
        # Only consume events that are within dialog bounds or are keyboard events
        if event_pos:
            return dialog_rect.collidepoint(event_pos)
        else:
            # For non-mouse events (like keyboard), consume them
            return True
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks"""
        # Check button clicks first
        if self.declare_button.collidepoint(mouse_pos) and self.selected_target:
            self._execute_charge()
            return True
        elif self.cancel_button.collidepoint(mouse_pos):
            self.hide()
            return True
        
        # Check target selection
        target_clicked = self._handle_target_click(mouse_pos)
        if target_clicked:
            return True
        
        # Click outside dialog - close it
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if not dialog_rect.collidepoint(mouse_pos):
            self.hide()
            return True
        
        return True
    
    def _handle_target_click(self, mouse_pos):
        """Handle clicks on target units"""
        if not self.available_targets:
            return False
        
        # Calculate target list area
        list_x = self.x + 20
        list_y = self.y + 160  # Increased to avoid overlap with unit info
        list_width = self.width - 40
        list_height = self.height - 240  # Adjusted for new layout
        
        if not (list_x <= mouse_pos[0] <= list_x + list_width and 
                list_y <= mouse_pos[1] <= list_y + list_height):
            return False
        
        # Calculate which target was clicked
        target_height = 60
        scroll_y = list_y - self.scroll_offset
        
        for i, target in enumerate(self.available_targets):
            target_rect = pygame.Rect(list_x, scroll_y + i * target_height, list_width, target_height)
            if target_rect.collidepoint(mouse_pos):
                # Only allow selection of valid targets
                if target in self.valid_targets:
                    self.selected_target = target
                    print(f"⚔️ Selected charge target: {target.name}")
                else:
                    print(f"❌ Cannot charge {target.name} - invalid target")
                return True
        
        return False
    
    def _execute_charge(self):
        """Execute the charge declaration"""
        if not self.selected_target or not self.callback:
            return
        
        # Execute the charge
        success = self.callback(self.unit, self.selected_target)
        
        if success:
            print(f"⚔️ Charge declared: {self.unit.name} charges {self.selected_target.name}")
        else:
            print(f"❌ Charge failed: {self.unit.name} could not charge {self.selected_target.name}")
        
        self.hide()
    
    def update_hover(self, mouse_pos):
        """Update hover states"""
        # Update button hover
        self.hovered_button = None
        if self.declare_button.collidepoint(mouse_pos) and self.selected_target:
            self.hovered_button = 'declare'
        elif self.cancel_button.collidepoint(mouse_pos):
            self.hovered_button = 'cancel'
        
        # Update target hover
        if not self.available_targets:
            self.hovered_target = -1
            return
        
        # Calculate target list area
        list_x = self.x + 20
        list_y = self.y + 160  # Increased to avoid overlap with unit info
        list_width = self.width - 40
        list_height = self.height - 240  # Adjusted for new layout
        
        if not (list_x <= mouse_pos[0] <= list_x + list_width and 
                list_y <= mouse_pos[1] <= list_y + list_height):
            self.hovered_target = -1
            return
        
        # Calculate which target is hovered
        target_height = 60
        scroll_y = list_y - self.scroll_offset
        
        for i, target in enumerate(self.available_targets):
            target_rect = pygame.Rect(list_x, scroll_y + i * target_height, list_width, target_height)
            if target_rect.collidepoint(mouse_pos):
                self.hovered_target = i
                return
        
        self.hovered_target = -1
    
    def scroll(self, delta):
        """Handle scroll wheel events"""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))
    
    def draw(self, screen):
        """Draw the charge declaration dialog"""
        if not self.visible or not self.unit:
            return
        
        # Draw semi-transparent overlay - only over the dialog area to avoid affecting battlefield
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (self.x, self.y))
        
        # Draw dialog background
        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, PANEL_BG, dialog_rect)
        pygame.draw.rect(screen, PANEL_BORDER, dialog_rect, 3)
        
        # Draw title
        title_text = self.font_large.render(f"Declare Charge - {self.unit.name}", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.x + self.width // 2, self.y + 30))
        screen.blit(title_text, title_rect)
        
        # Draw unit info
        self._draw_unit_info(screen)
        
        # Draw target list
        self._draw_target_list(screen)
        
        # Draw buttons
        self._draw_buttons(screen)
    
    def _draw_unit_info(self, screen):
        """Draw information about the charging unit"""
        info_y = self.y + 70  # Increased from 60
        
        # Unit status
        status_parts = []
        if self.unit.round_state.advanced_this_round:
            status_parts.append("Advanced")
        if self.unit.round_state.fell_back_this_round:
            status_parts.append("Fell Back")
        if self.unit.round_state.declared_charge_this_round:
            status_parts.append("Already Charged")
        
        if status_parts:
            status_text = f"Status: {', '.join(status_parts)}"
            status_color = WARNING_COLOR if any(s in status_parts for s in ["Advanced", "Fell Back", "Already Charged"]) else TEXT_SECONDARY
            status_surface = self.font_small.render(status_text, True, status_color)
            screen.blit(status_surface, (self.x + 20, info_y))
        else:
            status_surface = self.font_small.render("Status: Ready to charge", True, VALID_TARGET_COLOR)
            screen.blit(status_surface, (self.x + 20, info_y))
        
        # Charge distance
        charge_text = f"Max Charge Distance: {self.unit.max_charge_distance}\""
        charge_surface = self.font_small.render(charge_text, True, TEXT_SECONDARY)
        screen.blit(charge_surface, (self.x + 20, info_y + 20))
        
        # Unit position and movement info
        first_model = None
        for model in self.unit.models:
            if model.is_alive:
                first_model = model
                break

        if first_model:
            pos = first_model.get_location()
            pos_text = f"Position: ({pos[0]:.1f}, {pos[1]:.1f})"
            pos_surface = self.font_small.render(pos_text, True, TEXT_SECONDARY)
            screen.blit(pos_surface, (self.x + 20, info_y + 40))
        
        # Unit health
        health_text = f"Health: {self.unit.health_percent:.0f}%"
        health_surface = self.font_small.render(health_text, True, TEXT_SECONDARY)
        screen.blit(health_surface, (self.x + 350, info_y))  # Moved right to avoid overlap
        
        # Unit movement
        movement_text = f"Movement: {self.unit.movement}\""
        movement_surface = self.font_small.render(movement_text, True, TEXT_SECONDARY)
        screen.blit(movement_surface, (self.x + 350, info_y + 20))  # Moved right to avoid overlap
    
    def _draw_target_list(self, screen):
        """Draw the list of available targets"""
        list_x = self.x + 20
        list_y = self.y + 160  # Fixed position for header and list
        list_width = self.width - 40
        target_height = 60
        max_visible_targets = 5
        list_height = target_height * max_visible_targets  # Fixed height for 5 targets

        # Draw section title - always fixed
        title_text = self.font_medium.render("Available Targets", True, TEXT_PRIMARY)
        screen.blit(title_text, (list_x, list_y - 25))

        if not self.available_targets:
            no_targets_text = self.font_small.render("No targets available", True, TEXT_DISABLED)
            screen.blit(no_targets_text, (list_x, list_y + 20))
            return

        # Clamp scroll_offset to valid range
        max_scroll_offset = max(0, len(self.available_targets) - max_visible_targets)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll_offset))

        # Draw only the visible targets
        start_idx = self.scroll_offset
        end_idx = min(start_idx + max_visible_targets, len(self.available_targets))
        visible_targets = self.available_targets[start_idx:end_idx]

        for i, target in enumerate(visible_targets):
            target_rect = pygame.Rect(list_x, list_y + i * target_height, list_width, target_height)

            # Determine target color based on validity
            if target in self.valid_targets:
                bg_color = (40, 60, 40) if target == self.selected_target else (30, 45, 30)
                border_color = VALID_TARGET_COLOR if target == self.selected_target else (0, 150, 0)
            else:
                bg_color = (60, 40, 40) if target == self.selected_target else (45, 30, 30)
                border_color = INVALID_TARGET_COLOR if target == self.selected_target else (150, 0, 0)

            # Highlight hovered target
            global_idx = start_idx + i
            if global_idx == self.hovered_target:
                bg_color = tuple(min(255, c + 20) for c in bg_color)

            # Draw target background
            pygame.draw.rect(screen, bg_color, target_rect)
            pygame.draw.rect(screen, border_color, target_rect, 2)

            # Draw target name
            name_color = TEXT_PRIMARY if target in self.valid_targets else TEXT_DISABLED
            name_text = self.font_medium.render(target.name, True, name_color)
            screen.blit(name_text, (list_x + 10, list_y + i * target_height + 5))

            # Draw target info
            info_color = TEXT_SECONDARY if target in self.valid_targets else TEXT_DISABLED
            validation_info = self._get_target_validation_info(target)
            info_text = self.font_small.render(validation_info["reason"], True, info_color)
            screen.blit(info_text, (list_x + 10, list_y + i * target_height + 25))

            # Draw target health and position
            health_text = f"Health: {target.health_percent:.0f}%"
            health_color = TEXT_SECONDARY if target in self.valid_targets else TEXT_DISABLED
            health_surface = self.font_small.render(health_text, True, health_color)
            screen.blit(health_surface, (list_x + 10, list_y + i * target_height + 40))

            # Draw target position if available
            first_target_model = None
            for model in target.models:
                if model.is_alive:
                    first_target_model = model
                    break

            if first_target_model:
                pos = first_target_model.get_location()
                pos_text = f"Pos: ({pos[0]:.1f}, {pos[1]:.1f})"
                pos_surface = self.font_small.render(pos_text, True, info_color)
                screen.blit(pos_surface, (list_x + 250, list_y + i * target_height + 25))  # Moved right

            # Draw target movement if valid
            if target in self.valid_targets:
                movement_text = f"Move: {target.movement}\""
                movement_surface = self.font_small.render(movement_text, True, info_color)
                screen.blit(movement_surface, (list_x + 250, list_y + i * target_height + 40))  # Moved right

        # Update max_scroll for mouse wheel logic
        self.max_scroll = max_scroll_offset
    
    def _draw_buttons(self, screen):
        """Draw the dialog buttons"""
        # Declare Charge button
        declare_color = BUTTON_HOVER if self.hovered_button == 'declare' else BUTTON_BG
        declare_color = BUTTON_DISABLED if not self.selected_target else declare_color
        pygame.draw.rect(screen, declare_color, self.declare_button)
        pygame.draw.rect(screen, PANEL_BORDER, self.declare_button, 2)
        
        declare_text = self.font_medium.render("Declare Charge", True, TEXT_PRIMARY if self.selected_target else TEXT_DISABLED)
        declare_rect = declare_text.get_rect(center=self.declare_button.center)
        screen.blit(declare_text, declare_rect)
        
        # Cancel button
        cancel_color = BUTTON_HOVER if self.hovered_button == 'cancel' else BUTTON_BG
        pygame.draw.rect(screen, cancel_color, self.cancel_button)
        pygame.draw.rect(screen, PANEL_BORDER, self.cancel_button, 2)
        
        cancel_text = self.font_medium.render("Cancel", True, TEXT_PRIMARY)
        cancel_rect = cancel_text.get_rect(center=self.cancel_button.center)
        screen.blit(cancel_text, cancel_rect) 