import pygame
from typing import List, Optional, Callable
from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, BUTTON_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY

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


class ChargeDeclarationDialog(BaseDialog):
    """Dialog for declaring charges during the charge phase"""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=650, height=550, draggable=True, center=True)
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        self.decision_request = None
        
        # Fonts are provided by BaseDialog (font_large, font_medium, font_small)
        
        # Available targets
        self.available_targets = []
        self.valid_targets = []
        self.invalid_targets = []
        
        # UI state
        self.scroll_offset = 0
        self.max_scroll = 0
        self.hovered_target = -1
        self.selected_target = None
        self.selected_targets = set()
        
        # Button rectangles - made wider
        button_width = 140  # Increased from 120
        button_height = 35
        button_spacing = 20  # Increased spacing
        
        start_x = self.x + (self.width - (2 * button_width + button_spacing)) // 2
        button_y = self.y + self.height - 50
        
        self.declare_button = pygame.Rect(start_x, button_y, button_width, button_height)
        self.cancel_button = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)
        
        self.hovered_button = None
    
    def show(self, unit, callback, game_map=None, game_view=None, decision_request=None):
        """Show the charge declaration dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.game_view = game_view
        self.decision_request = decision_request
        # IMPORTANT: pass callback so BaseDialog.callback is preserved
        super().show(callback)
        
        # Clear previous state
        self.selected_target = None
        self.selected_targets = set()
        self.scroll_offset = 0
        self.hovered_target = -1
        
        # Keep centered; dialog is draggable
        
        # Create BaseDialog buttons (relative coordinates)
        button_width = 140
        button_height = 35
        button_spacing = 20
        rel_start_x = (self.width - (2 * button_width + button_spacing)) // 2
        rel_y = self.height - 50
        # Add buttons via BaseDialog so clicks are handled uniformly
        self.add_button('declare', rel_start_x, rel_y, button_width, button_height, enabled=False)
        self.add_button('cancel', rel_start_x + button_width + button_spacing, rel_y, button_width, button_height, enabled=True)
        
        # Get available targets
        self._update_available_targets()
        
        # Calculate scroll limits
        target_count = len(self.available_targets)
        target_height = 60
        total_height = target_count * target_height
        visible_height = self.height - 240  # Account for header, unit info, and buttons (160 + 240 = 400)
        self.max_scroll = max(0, total_height - visible_height)
        
        print(f"INFO: ChargeDeclarationDialog shown for {unit.name}")
        print(f"INFO: Found {len(self.valid_targets)} valid targets")
        print(f"ERROR: Found {len(self.invalid_targets)} invalid targets")
        
        # Check if unit is eligible to charge
        if not self._is_unit_eligible_to_charge():
            print(f"ERROR: {unit.name} is not eligible to charge")
            self.hide()
            return
    
    def hide(self):
        """Hide the charge declaration dialog"""
        super().hide()
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        self.available_targets = []
        self.valid_targets = []
        self.invalid_targets = []
        self.selected_target = None
        self.selected_targets = set()
        self.scroll_offset = 0
        self.hovered_target = -1
        self.decision_request = None
    
    def _update_available_targets(self):
        """Update the list of available targets"""
        if not self.game_map or not self.unit:
            return

        if self.decision_request is not None and self.game_view is not None:
            registry = getattr(self.game_view.game, "entity_registry", None)
            options = list(getattr(self.decision_request, "options", []) or [])
            seen = set()
            self.valid_targets = []
            self.invalid_targets = []
            for opt in options:
                payload = dict(getattr(opt, "payload", {}) or {})
                target_id = str(payload.get("target_unit_id", "") or "")
                if not target_id or target_id in seen:
                    continue
                seen.add(target_id)
                target = registry.get(target_id, kind="unit") if registry is not None else None
                if target is None:
                    continue
                if bool(payload.get("valid", True)):
                    self.valid_targets.append(target)
                else:
                    self.invalid_targets.append(target)
            self.available_targets = self.valid_targets + self.invalid_targets
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
            print(f"ERROR: Charge eligibility check failed: No unit selected")
            return False
        try:
            game = getattr(self.game_view, "game", None)
        except Exception:
            game = None
        if game is None:
            print(f"ERROR: Charge eligibility check failed: No game context")
            return False
        eligible = bool(self.unit.can_declare_charge(game))
        if not eligible:
            print(f"ERROR: {self.unit.name} is not eligible to charge")
        return eligible

    def _get_charge_modifiers(self, target):
        if not self.unit or not self.game_view:
            return []
        game = getattr(self.game_view, "game", None)
        if game is None:
            return []
        getter = getattr(game, "get_charge_roll_modifiers", None)
        if not callable(getter):
            return []
        return list(getter(self.unit, target_unit=target) or [])

    def _get_max_charge_distance(self, target) -> float:
        base = float(getattr(self.unit, "max_charge_distance", 0) or 0)
        if not self.game_view:
            return base
        game = getattr(self.game_view, "game", None)
        if game is None:
            return base
        getter = getattr(game, "get_max_charge_distance", None)
        if not callable(getter):
            return base
        return float(getter(self.unit, target_unit=target))

    def _format_charge_modifiers(self, modifiers) -> str:
        parts = []
        for val, source in list(modifiers or []):
            if not isinstance(val, (int, float)):
                continue
            num = int(val)
            if not num:
                continue
            label = str(source or "").strip()
            if label:
                parts.append(f"{num:+d} {label}")
            else:
                parts.append(f"{num:+d}")
        return ", ".join(parts)
    
    def _get_target_validation_info(self, target):
        """Get validation information for a target"""
        if not self.unit or not target:
            return {"valid": False, "reason": "Invalid target"}
        
        # Check if unit is alive
        if not target.is_alive():
            return {"valid": False, "reason": "Target is destroyed"}
        
        # Check if unit has already charged
        if self.unit.round_state.attempted_charge_this_round:
            return {"valid": False, "reason": "Unit has already attempted a charge this round"}

        try:
            game = getattr(self.game_view, "game", None)
        except Exception:
            game = None
        if game is None or not self.unit.can_declare_charge(game):
            return {"valid": False, "reason": "Unit is not eligible to charge"}
        
        # Check if unit advanced this round
        if self.unit.round_state.advanced_this_round:
            if not self.unit.can_charge_after_advance():
                return {"valid": False, "reason": "Unit advanced and cannot charge"}
        
        # Check if unit fell back this round
        if self.unit.round_state.fell_back_this_round:
            if not self.unit.can_charge_after_fall_back():
                return {"valid": False, "reason": "Unit fell back and cannot charge"}
        
        # Check if unit is already in engagement range of any enemy
        try:
            enemy_units = self.game_map.get_enemy_units(self.unit)
        except Exception:
            enemy_units = []
        if any(self.game_map.is_within_engagement_range(self.unit, enemy)
               for enemy in enemy_units if enemy.is_alive()):
            return {"valid": False, "reason": "Unit is already in engagement range"}
        
        # Check distance
        distance = self.game_map.get_distance_between_units(self.unit, target)
        max_distance = self._get_max_charge_distance(target)
        modifiers = self._get_charge_modifiers(target)
        mod_text = self._format_charge_modifiers(modifiers)
        if distance > max_distance:
            reason = f"Target too far ({distance:.1f}\" > {max_distance:.1f}\")"
            if mod_text:
                reason = f"{reason} mods: {mod_text}"
            return {"valid": False, "reason": reason}
        
        # Check if path is blocked (simplified)
        if self.game_map.is_path_blocked(self.unit, target):
            return {"valid": False, "reason": "Path to target is blocked"}
        
        reason = f"Distance: {distance:.1f}\" (max {max_distance:.1f}\")"
        if mod_text:
            reason = f"{reason} mods: {mod_text}"
        return {"valid": True, "reason": reason}
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        # Use BaseDialog handling for drag/title/ESC
        if super().handle_event(event):
            return True
        # Local scroll
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + (30 if event.button == 5 else -30)))
            return True
        # ENTER to execute
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN and self.selected_targets:
            self._execute_charge()
            return True
        return False
    
    def _handle_dialog_click(self, mouse_pos) -> bool:
        """Handle clicks inside dialog area for target selection."""
        # Delegate to target list selection; BaseDialog handles button clicks separately
        return self._handle_target_click(mouse_pos)
    
    def _handle_target_click(self, mouse_pos):
        """Handle clicks on target units"""
        if not self.available_targets:
            return False
        
        # Calculate target list area (below title and unit info)
        list_x = self.x + 20
        list_y = self.y + self.title_bar_height + 110
        list_width = self.width - 40
        list_height = self.height - (self.title_bar_height + 200)
        
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
                    if target in self.selected_targets:
                        self.selected_targets.remove(target)
                        print(f"INFO: Deselected charge target: {target.name}")
                    else:
                        self.selected_targets.add(target)
                        print(f"INFO: Selected charge target: {target.name}")
                else:
                    print(f"ERROR: Cannot charge {target.name} - invalid target")
                return True
        
        return False
    
    def _execute_charge(self):
        """Execute the charge declaration"""
        if not self.selected_targets or not self.callback:
            return
        targets = list(self.selected_targets)
        # Execute the charge
        success = self.callback(self.unit, targets)
        
        if success:
            target_names = ", ".join(getattr(t, "name", "Target") for t in targets)
            print(f"INFO: Charge declared: {self.unit.name} charges {target_names}")
        else:
            print(f"ERROR: Charge failed: {self.unit.name} could not charge selected targets")
        
        self.hide()
    
    def update_hover(self, mouse_pos):
        """Update hover states"""
        # Update button hover
        self.hovered_button = None
        if self.declare_button.collidepoint(mouse_pos) and self.selected_targets:
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
        
        # Draw dialog background and title bar
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, f"Declare Charge - {self.unit.name}")
        
        # Draw unit info
        self._draw_unit_info(screen)
        
        # Draw target list
        self._draw_target_list(screen)
        
        # Draw buttons (enable/disable declare based on selection)
        if 'declare' in self.button_states:
            self.button_states['declare']['enabled'] = bool(self.selected_targets)
        self.draw_button(screen, 'declare', 'Declare Charge')
        self.draw_button(screen, 'cancel', 'Cancel')
    
    def _draw_unit_info(self, screen):
        """Draw information about the charging unit"""
        info_y = self.y + 70  # Increased from 60
        
        # Unit status
        status_parts = []
        if self.unit.round_state.advanced_this_round:
            status_parts.append("Advanced")
        if self.unit.round_state.fell_back_this_round:
            status_parts.append("Fell Back")
        if self.unit.round_state.attempted_charge_this_round:
            status_parts.append("Already Attempted Charge")
        
        if status_parts:
            status_text = f"Status: {', '.join(status_parts)}"
            status_color = WARNING_COLOR if any(s in status_parts for s in ["Advanced", "Fell Back", "Already Attempted Charge"]) else TEXT_SECONDARY
            status_surface = self.font_small.render(status_text, True, status_color)
            screen.blit(status_surface, (self.x + 20, info_y))
        else:
            status_surface = self.font_small.render("Status: Ready to charge", True, VALID_TARGET_COLOR)
            screen.blit(status_surface, (self.x + 20, info_y))
        
        # Charge distance
        if self.selected_targets:
            targets = list(self.selected_targets)
            max_distance = min(self._get_max_charge_distance(t) for t in targets)
            modifiers = []
            for t in targets:
                modifiers.extend(self._get_charge_modifiers(t))
            mod_text = self._format_charge_modifiers(modifiers)
            charge_text = f"Max Charge Distance: {max_distance:.1f}\""
            if mod_text:
                charge_text = f"{charge_text} ({mod_text})"
        else:
            max_distance = float(getattr(self.unit, "max_charge_distance", 0) or 0)
            mod_hint = ""
            if any(self._get_charge_modifiers(t) for t in self.valid_targets):
                mod_hint = " (mods vary by target)"
            charge_text = f"Max Charge Distance: {max_distance:.1f}\"{mod_hint}"
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
        list_y = self.y + self.title_bar_height + 110
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
            is_selected = target in self.selected_targets
            if target in self.valid_targets:
                bg_color = (40, 60, 40) if is_selected else (30, 45, 30)
                border_color = VALID_TARGET_COLOR if is_selected else (0, 150, 0)
            else:
                bg_color = (60, 40, 40) if is_selected else (45, 30, 30)
                border_color = INVALID_TARGET_COLOR if is_selected else (150, 0, 0)

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
    
    def _handle_button_click(self, button_name: str) -> bool:
        """Satisfy BaseDialog requirement; map to local buttons if needed."""
        if button_name == 'declare':
            if self.selected_targets:
                names = ", ".join(getattr(t, "name", "Target") for t in self.selected_targets)
                print(f"DEBUG: Declare pressed with selected targets: {names}")
                self._execute_charge()
                return True
            else:
                print("DEBUG: Declare pressed but no target selected")
                return False
        if button_name == 'cancel':
            self.hide()
            return True
        return False
    
    # Legacy draw removed; BaseDialog.draw_button is used in draw()
