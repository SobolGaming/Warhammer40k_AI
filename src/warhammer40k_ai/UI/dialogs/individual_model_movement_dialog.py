import pygame
import re
import math
from typing import List, Optional, Callable, Dict, Any
from .base_dialog import BaseDialog, TEXT_SUCCESS, TEXT_WARNING, BUTTON_SELECTED
from ...utility.constants import RUINS_FLOOR_HEIGHT
from ...utility.placement_validation import bases_overlap_3d

# Additional colors specific to this dialog
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow for model highlighting


class IndividualModelMovementDialog(BaseDialog):
    """Dialog for moving individual models within a unit during movement phases"""
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=600, height=400, draggable=True)
        
        # Dialog-specific state
        self.unit = None
        self.movement_type = None  # 'move', 'advance', 'fall_back', 'scout', 'pile_in', 'consolidate', 'charge', 'reactive', 'loping_speed'
        self.game_map = None
        self.max_distance = 0.0
        self.target_unit = None  # Target unit for charge movement
        
        # Model movement tracking
        self.model_movements = {}  # {model_index: {'path': [...], 'completed': bool}}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        # Floor selection sub-dialog state
        self.floor_selection_dialog = None
        self._pending_click_position = None  # (x,y) waiting for floor selection
        self._pending_floor_z_by_level = None  # {level: z} for the pending click

        # Deployment placement facing (radians). Used for hover silhouette + final placement.
        self._deploy_facing_radians: Optional[float] = None
        # Optional custom placement validator for deploy-like placement.
        self.placement_validator = None
        
        # UI elements
        self.model_buttons = []
        
    def show(self, unit, movement_type: str, callback: Callable, game_map, max_distance: float = None, target_unit=None, placement_validator: Optional[Callable] = None):
        """Show the dialog for the given unit and movement type"""

        # Check if unit has already moved this round (prevent multiple movements)
        if self._has_unit_already_moved(unit, movement_type):
            print(f"❌ {unit.name} has already performed {movement_type} movement this round")
            if callback:
                callback(False)  # Movement not allowed
            return

        # Call parent show method
        super().show(callback)

        # Dialog-specific initialization
        # If this unit is an Attached unit (bodyguard + leader(s)), use a proxy with combined models.
        try:
            from warhammer40k_ai.units.attached_unit import AttachedUnitView
        except Exception:
            AttachedUnitView = None

        self._attached_members = None
        if AttachedUnitView is not None:
            try:
                members = unit.get_attached_unit_members()
                if members and len(members) > 1:
                    self.unit = AttachedUnitView(unit.get_attached_unit_root())
                    self._attached_members = list(getattr(self.unit, "members", []) or [])
                else:
                    self.unit = unit
            except Exception:
                self.unit = unit
        else:
            self.unit = unit
        self.movement_type = movement_type
        self.game_map = game_map
        self.max_distance = max_distance or unit.movement
        self.target_unit = target_unit
        self.placement_validator = placement_validator

        # Reset movement tracking
        self.model_movements = {}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        if movement_type != 'deploy':
            self._deploy_facing_radians = None

        # Publish unit move started (for Stratagem reactions like Overwatch)
        # NOTE: Do NOT publish for deployment placement.
        if self.movement_type not in ('deploy', 'reactive', 'blood_surge', 'loping_speed'):
            try:
                _player = getattr(self.unit.get_parent_army(), 'player', None)
                _game = getattr(_player, 'game', None) if _player else None
                if _game and hasattr(_game, 'event_system'):
                    action = 'move'
                    if self.movement_type == 'advance':
                        action = 'advance'
                    elif self.movement_type == 'fall_back':
                        action = 'fall_back'
                    elif self.movement_type == 'charge':
                        action = 'charge'
                    _game.event_system.publish("unit_move_started", unit=self.unit, action=action)
            except Exception:
                pass

        # Initialize model buttons and dialog buttons
        self._create_model_buttons()
        self._create_dialog_buttons()

        print(f"🎯 Individual model movement dialog opened for {unit.name} ({movement_type})")
        print(f"📍 Select a model, then click on the battlefield to move it")

        # In deploy mode, auto-select the first alive model and wait for battlefield click
        if self.movement_type == 'deploy':
            for idx, m in enumerate(self.unit.models):
                if getattr(m, 'is_alive', True):
                    self._select_model(idx)
                    break

    def _has_unit_already_moved(self, unit, movement_type: str) -> bool:
        """Check if unit has already performed this type of movement this round"""
        if movement_type == 'move':
            return unit.round_state.moved_this_round
        elif movement_type == 'advance':
            return unit.round_state.advanced_this_round or unit.round_state.moved_this_round
        elif movement_type == 'fall_back':
            return unit.round_state.fell_back_this_round or unit.round_state.moved_this_round
        elif movement_type == 'scout':
            # Scout moves happen before the game starts, different tracking needed
            return False  # For now, allow scout moves
        elif movement_type == 'reactive':
            return False
        elif movement_type == 'loping_speed':
            return False
        elif movement_type == 'deploy':
            return False
        elif movement_type in ['pile_in', 'consolidate']:
            # These are fight phase movements, different rules
            return False  # For now, allow these
        elif movement_type == 'charge':
            # For charge movement, check if the unit has already completed charge movement
            # A unit that has declared a charge should be allowed to perform the movement
            return getattr(unit.round_state, 'charged_this_round', False)
        else:
            return unit.round_state.moved_this_round
        
    def hide(self):
        """Hide the dialog"""
        super().hide()
        
        # Clean up dialog-specific state
        self.unit = None
        self._attached_members = None
        self.movement_type = None
        self.game_map = None
        self.max_distance = 0.0
        self.target_unit = None
        self.model_movements = {}
        self.selected_model_index = None
        self.awaiting_battlefield_click = False
        self._deploy_facing_radians = None
        self.placement_validator = None
        # Hide nested dialogs as well
        if hasattr(self, 'floor_selection_dialog') and self.floor_selection_dialog:
            self.floor_selection_dialog.hide()
        
    def _create_model_buttons(self):
        """Create buttons for each model in the unit"""
        self.model_buttons = []
        
        if not self.unit or not self.unit.models:
            return
            
        # Calculate button layout
        # Compute width from dialog size so labels have maximum room
        start_x = 20  # Relative to dialog
        start_y = 80  # Relative to dialog
        button_height = 30
        button_spacing = 5
        models_per_row = 3

        usable_width = max(0, int(self.width - (start_x * 2)))
        button_width = max(120, int((usable_width - (button_spacing * (models_per_row - 1))) / models_per_row))
        
        button_index = 0  # Separate index for button positioning
        for i, model in enumerate(self.unit.models):
            if not model.is_alive:
                continue
            
            # Models already in base-to-base contact cannot Pile In or Consolidate
            in_base_contact = self.movement_type in ('pile_in', 'consolidate') and self._is_model_in_base_contact(model)
            if in_base_contact:
                print(f"🔍 DEBUG: {model.name} already in base contact - will be shown as disabled")
                
            row = button_index // models_per_row
            col = button_index % models_per_row
            
            button_x = start_x + col * (button_width + button_spacing)
            button_y = start_y + row * (button_height + button_spacing)
            
            # Store relative position for re-positioning during drag
            self.model_buttons.append({
                'rect': pygame.Rect(self.x + button_x, self.y + button_y, button_width, button_height),
                'model_index': i,  # Keep original model index
                'model': model,
                'relative_x': button_x,
                'relative_y': button_y,
                'width': button_width,
                'height': button_height,
                'disabled': in_base_contact,  # Mark as disabled if in base contact
                'disabled_reason': 'Already in base contact' if in_base_contact else None
            })
            
            button_index += 1

    def _truncate_text_to_width(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        """Truncate text with ellipsis so it fits within max_width."""
        try:
            if max_width <= 0:
                return ""
            if font.size(text)[0] <= max_width:
                return text
            ell = "..."
            ell_w = font.size(ell)[0]
            if ell_w >= max_width:
                return ""
            lo, hi = 0, len(text)
            # binary search for the longest prefix that fits
            while lo < hi:
                mid = (lo + hi) // 2
                candidate = text[:mid].rstrip() + ell
                if font.size(candidate)[0] <= max_width:
                    lo = mid + 1
                else:
                    hi = mid
            # lo is first that fails; use lo-1
            candidate = text[: max(0, lo - 1)].rstrip() + ell
            # Ensure fit
            while candidate and font.size(candidate)[0] > max_width:
                candidate = candidate[:-4].rstrip() + ell if len(candidate) > 3 else ""
            return candidate
        except Exception:
            return text

    def _truncate_middle_preserve_suffix(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        """Middle-truncate so the suffix (e.g. ' 1', ' 10') remains visible."""
        try:
            if max_width <= 0:
                return ""
            if font.size(text)[0] <= max_width:
                return text

            # Prefer preserving a trailing " <digits>" suffix if present, otherwise last 2 chars
            m = re.search(r"(\s+\d+)$", text)
            if m:
                suffix = m.group(1)
                prefix = text[: -len(suffix)]
            else:
                suffix = text[-2:]
                prefix = text[:-2]

            mid = " .. "
            # If even the minimal form doesn't fit, fall back to simple truncation
            minimal = (suffix or "").strip()
            if not prefix:
                return self._truncate_text_to_width(text, font, max_width)
            if font.size(mid + suffix)[0] >= max_width:
                return self._truncate_text_to_width(text, font, max_width)

            # Binary search how much prefix we can keep
            lo, hi = 0, len(prefix)
            best = ""
            while lo <= hi:
                mid_i = (lo + hi) // 2
                candidate = prefix[:mid_i].rstrip() + mid + suffix.lstrip()
                if font.size(candidate)[0] <= max_width:
                    best = candidate
                    lo = mid_i + 1
                else:
                    hi = mid_i - 1

            return best if best else self._truncate_text_to_width(text, font, max_width)
        except Exception:
            return self._truncate_text_to_width(text, font, max_width)
    
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
                # Check if button is disabled
                if button.get('disabled', False):
                    print(f"⚠️  Cannot select {button['model'].name}: {button.get('disabled_reason', 'Model unavailable')}")
                    return True
                
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

        # In deploy mode, keep a persistent facing for the whole unit placement sequence.
        if self.movement_type == 'deploy':
            try:
                if self._deploy_facing_radians is None:
                    inferred = None
                    try:
                        inferred = self._infer_default_deploy_facing_radians(model)
                    except Exception:
                        inferred = None
                    if inferred is not None:
                        self._deploy_facing_radians = float(inferred)
                    else:
                        self._deploy_facing_radians = float(getattr(model.model_base, 'facing', 0.0))
            except Exception:
                if self._deploy_facing_radians is None:
                    self._deploy_facing_radians = 0.0
        
        print(f"🎯 Selected {model.name} (Model #{model_index + 1}) for {self.movement_type} movement")
        print(f"📍 Click on the battlefield to move this model")

    def _infer_default_deploy_facing_radians(self, model) -> Optional[float]:
        """Infer default deploy facing from the active player's deployment zone geometry.

        Left/right zones:
        - left zone faces right (+X)
        - right zone faces left (-X)

        Top/bottom zones:
        - top zone faces down (+Y)
        - bottom zone faces up (-Y)
        """
        try:
            game = model.parent_unit.get_parent_army().player.game
        except Exception:
            game = None
        if game is None:
            return None

        try:
            player_name = model.parent_unit.get_parent_army().player.name
        except Exception:
            player_name = None
        if not player_name:
            return None

        zone_info = getattr(game, "deployment_zones", {}) or {}
        z = zone_info.get(player_name) if isinstance(zone_info, dict) else None
        mission_zones = (z or {}).get("mission_zones") if isinstance(z, dict) else None
        if not mission_zones:
            return None

        # Gather bounds from all mission zone vertices
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        found = False
        for mz in mission_zones:
            verts = getattr(mz, "vertices", None) or []
            for vx, vy in verts:
                found = True
                min_x = min(min_x, float(vx))
                max_x = max(max_x, float(vx))
                min_y = min(min_y, float(vy))
                max_y = max(max_y, float(vy))
        if not found:
            return None

        try:
            bf_w, bf_h = game.get_battlefield_size()
            bf_w = float(bf_w)
            bf_h = float(bf_h)
        except Exception:
            # Fallback to Strike Force (inches)
            bf_w, bf_h = 60.0, 44.0

        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        extent_x = max_x - min_x
        extent_y = max_y - min_y

        # If the zone is a tall strip, it’s likely left/right; if wide strip, likely top/bottom.
        if extent_x <= extent_y:
            return 0.0 if cx < (bf_w / 2.0) else math.pi
        else:
            return (math.pi / 2.0) if cy < (bf_h / 2.0) else (3.0 * math.pi / 2.0)
        
    def get_deploy_facing_radians(self) -> float:
        """Facing used for deployment hover silhouette + final placement (radians)."""
        try:
            if self._deploy_facing_radians is None:
                return 0.0
            return float(self._deploy_facing_radians)
        except Exception:
            return 0.0

    def rotate_deploy_facing_degrees(self, delta_degrees: float) -> None:
        """Adjust deployment facing (in 5° increments typically). No-op outside deploy mode."""
        if self.movement_type != 'deploy':
            return
        try:
            if self._deploy_facing_radians is None:
                # initialize from selected model if possible
                if self.selected_model_index is not None and self.unit and self.selected_model_index < len(self.unit.models):
                    m = self.unit.models[self.selected_model_index]
                    self._deploy_facing_radians = float(getattr(m.model_base, 'facing', 0.0))
                else:
                    self._deploy_facing_radians = 0.0
            self._deploy_facing_radians = (float(self._deploy_facing_radians) + math.radians(float(delta_degrees))) % (2.0 * math.pi)
        except Exception:
            # fail-safe: don't crash input handling
            try:
                self._deploy_facing_radians = float(self._deploy_facing_radians or 0.0)
            except Exception:
                self._deploy_facing_radians = 0.0

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

        # DEPLOY: rotate facing via mouse wheel (5° increments). We handle this directly in the dialog so it
        # works even when the dialog is modal (DialogManager blocks wheel events by default).
        try:
            if getattr(self, "movement_type", "") == "deploy" and self.selected_model_index is not None:
                if getattr(event, "type", None) == pygame.MOUSEWHEEL:
                    self.rotate_deploy_facing_degrees(float(getattr(event, "y", 0.0)) * 5.0)
                    return True
                if getattr(event, "type", None) == pygame.MOUSEBUTTONDOWN and getattr(event, "button", None) in (4, 5):
                    delta = 5.0 if int(getattr(event, "button", 0)) == 4 else -5.0
                    self.rotate_deploy_facing_degrees(delta)
                    return True
        except Exception:
            pass

        # Debug: Log all events handled by this dialog
        # TODO: Uncomment for event debugging
        # dialog_name = self.__class__.__name__
        # if event.type == pygame.KEYDOWN:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - KEYDOWN: key={pygame.key.name(event.key)}")
        # elif event.type == pygame.MOUSEBUTTONDOWN:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEBUTTONDOWN: button={event.button}, pos={event.pos}")
        # elif event.type == pygame.MOUSEBUTTONUP:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEBUTTONUP: button={event.button}, pos={event.pos}")
        # elif event.type == pygame.MOUSEMOTION:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - MOUSEMOTION: pos={event.pos}")
        # else:
        #     print(f"🔍 DEBUG: {dialog_name}.handle_event - OTHER: type={event.type}")

        # Handle coherency dialog events first if it's open
        if hasattr(self, 'coherency_dialog') and self.coherency_dialog.visible:
            # print(f"🔍 DEBUG: {dialog_name} - Delegating to coherency dialog")
            return self.coherency_dialog.handle_event(event)

        # Handle floor selection dialog if open
        if hasattr(self, 'floor_selection_dialog') and self.floor_selection_dialog and self.floor_selection_dialog.visible:
            result = self.floor_selection_dialog.handle_event(event)
            if result:
                action = result.get('action')
                if action == 'confirm':
                    selected_level = result.get('floor', 0)
                    # Convert selected level to Z (prefer pending mapping if available)
                    surface_z = float(selected_level) * float(RUINS_FLOOR_HEIGHT)
                    try:
                        if isinstance(self._pending_floor_z_by_level, dict) and selected_level in self._pending_floor_z_by_level:
                            surface_z = float(self._pending_floor_z_by_level[selected_level])
                    except Exception:
                        pass
                    if self._pending_click_position is not None:
                        dest_x, dest_y = self._pending_click_position
                        self.floor_selection_dialog.hide()
                        # Proceed with move/deploy using selected Z
                        if self.movement_type == 'deploy':
                            self._finalize_deploy_click_with_z(dest_x, dest_y, surface_z)
                        else:
                            self._finalize_click_with_z(dest_x, dest_y, surface_z)
                        self._pending_click_position = None
                        self._pending_floor_z_by_level = None
                        return True
                elif action == 'cancel':
                    # Cancel selection; do nothing (user can click again)
                    self.floor_selection_dialog.hide()
                    self._pending_click_position = None
                    self._pending_floor_z_by_level = None
                    return True
            # IMPORTANT: While floor selection is visible, consume ALL events here
            # to prevent battlefield clicks from placing models underneath.
            return True

        # Handle ESC key to close dialog
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # print(f"🔍 DEBUG: {dialog_name} - ESC key pressed, hiding dialog")
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

    def should_passthrough_event(self, event: pygame.event.Event) -> bool:
        """
        Hint for DialogManager: allow the phase handler to receive certain events when this dialog
        intentionally returns False.

        This is required for battlefield clicks during per-model movement/deployment:
        the phase handler converts screen->game coords and calls handle_battlefield_click().
        """
        try:
            if not self.visible:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", None) == 1:
                if self.awaiting_battlefield_click:
                    mouse_pos = getattr(event, "pos", None)
                    if mouse_pos:
                        dialog_rect = pygame.Rect(self.x, self.y, self.width, self.height)
                        if not dialog_rect.collidepoint(mouse_pos):
                            return True
        except Exception:
            return False
        return False
    
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
        """Handle battlefield click for model movement or deployment.

        If movement_type is 'deploy', validate using deployment rules per model, not movement rules.
        """
        if not self.awaiting_battlefield_click or self.selected_model_index is None:
            return False

        # If a floor selection dialog is open, ignore battlefield clicks until resolved.
        if getattr(self, 'floor_selection_dialog', None) is not None and getattr(self.floor_selection_dialog, 'visible', False):
            try:
                print("🏢 Floor selection pending - ignoring battlefield click until confirm/cancel")
            except Exception:
                pass
            return True

        # If multiple RUINS floors are valid for this model's BASE at this XY, ask user to pick a floor
        try:
            model = self.unit.models[self.selected_model_index]
        except Exception:
            model = None
        floors_at_xy: list[int] = []
        z_by_level: dict[int, float] = {}
        disabled_by_validation: list[int] = []
        if model is not None:
            floors_at_xy, z_by_level, disabled_by_validation = self._get_ruins_floor_options_for_model_at_xy(model, battlefield_x, battlefield_y)

        # If this RUINS has multiple floors at all, ask user to pick a floor.
        # Floors that aren't valid at this XY (overhang/walls/clearance/unit restrictions) are shown but disabled.
        if len(floors_at_xy) > 1:
            disabled: list[int] = list(disabled_by_validation or [])
            # For movement/pathing: list all valid floors but disable unreachable ones by distance
            if self.movement_type != 'deploy':
                try:
                    from ...utility.calcs import get_dist
                    current_pos = model.get_location() if model is not None else None
                    if current_pos:
                        for lvl in floors_at_xy:
                            z = float(z_by_level.get(lvl, float(lvl) * float(RUINS_FLOOR_HEIGHT)))
                            d = get_dist(battlefield_x - current_pos[0], battlefield_y - current_pos[1], z - (current_pos[2] if len(current_pos) > 2 else 0.0))
                            if d > float(self.max_distance):
                                if lvl not in disabled:
                                    disabled.append(lvl)
                except Exception:
                    # keep validation-based disables even if distance calc fails
                    disabled = list(disabled_by_validation or [])
            try:
                mname = getattr(model, 'name', 'Unknown model')
                print(
                    f"🏢 RUINS floor selection triggered for {self.unit.name} / {mname} "
                    f"at ({battlefield_x:.1f}, {battlefield_y:.1f}). "
                    f"floors={floors_at_xy}, disabled={sorted(disabled)} (movement_type={self.movement_type})"
                )
            except Exception:
                pass
            try:
                from .floor_selection_dialog import FloorSelectionDialog
                dialog = FloorSelectionDialog(available_floors=floors_at_xy, unit_name=self.unit.name, disabled_floors=disabled)
                self.floor_selection_dialog = dialog
                self._pending_click_position = (battlefield_x, battlefield_y)
                self._pending_floor_z_by_level = dict(z_by_level or {})
                dialog.show()
                try:
                    print(f"🏢 Floor selection dialog visible={getattr(dialog, 'visible', None)}")
                except Exception:
                    pass
                return True  # Defer until selection
            except Exception as e:
                try:
                    print(f"❌ Floor selection dialog failed to open: {e}")
                except Exception:
                    pass
                # If UI fails, fall back to using provided Z
                self._pending_floor_z_by_level = None

        # Use provided Z if no selection needed (or single floor)
        destination = (battlefield_x, battlefield_y, battlefield_z)

        # If we're in deployment mode, run deployment validation and place the model directly
        if self.movement_type == 'deploy':
            model = self.unit.models[self.selected_model_index]
            # Validate single model deployment
            try:
                game = model.parent_unit.get_parent_army().player.game
            except Exception:
                game = None
            if not game:
                print("❌ Deployment failed: game context unavailable")
                return False
            # Determine player by unit ownership
            try:
                player_name = model.parent_unit.get_parent_army().player.name
            except Exception:
                player_name = ''
            validation = self._validate_deploy_like_placement(game, model, battlefield_x, battlefield_y, battlefield_z, player_name)
            if not validation['valid']:
                try:
                    facing_deg = math.degrees(self.get_deploy_facing_radians())
                except Exception:
                    facing_deg = 0.0
                print(
                    f"❌ Deployment invalid for {model.name} at "
                    f"({battlefield_x:.1f}, {battlefield_y:.1f}, {battlefield_z:.1f}) facing={facing_deg:.1f}°: "
                    f"{validation['reason']}"
                )
                return False

            # Prevent illegal base overlaps during deployment.
            # This must consider already-placed models in the same unit (unit may not be registered on the map yet).
            overlap_validation = self._validate_deployment_no_base_overlap(
                model=model,
                x=battlefield_x,
                y=battlefield_y,
                z=battlefield_z,
                facing=self.get_deploy_facing_radians(),
            )
            if not overlap_validation['valid']:
                try:
                    facing_deg = math.degrees(self.get_deploy_facing_radians())
                except Exception:
                    facing_deg = 0.0
                print(
                    f"❌ Deployment invalid for {model.name} at "
                    f"({battlefield_x:.1f}, {battlefield_y:.1f}, {battlefield_z:.1f}) facing={facing_deg:.1f}°: "
                    f"{overlap_validation['reason']}"
                )
                return False

            # Place the model at destination (preserve facing)
            current_facing = self.get_deploy_facing_radians()
            model.set_location(destination[0], destination[1], destination[2], float(current_facing))
            print(f"✅ {model.name} deployed to ({destination[0]:.1f}, {destination[1]:.1f}{'' if abs(destination[2]) < 1e-6 else f', {destination[2]:.1f}'})")
            success = True
        else:
            # Attempt to move the selected model (non-deployment movement)
            success = self._move_model(self.selected_model_index, destination)
        
        if success:
            # Mark model as moved
            self.model_movements[self.selected_model_index] = {
                'path': [],  # Path would be stored here if needed
                'completed': True
            }
            
            # Check if all models are moved
            if self._all_models_moved():
                done_word = 'deployed' if self.movement_type == 'deploy' else 'moved'
                print(f"✅ All models in {self.unit.name} have been {done_word}")
                # Auto-complete after short delay or continue allowing more moves
                
            # In deploy mode, immediately advance to the next unplaced alive model
            if self.movement_type == 'deploy':
                next_idx = None
                for idx, m in enumerate(self.unit.models):
                    if not getattr(m, 'is_alive', True):
                        continue
                    if idx in self.model_movements and self.model_movements[idx].get('completed', False):
                        continue
                    next_idx = idx
                    break

                if next_idx is not None:
                    self._select_model(next_idx)
                else:
                    self.selected_model_index = None
                    self.awaiting_battlefield_click = False
            else:
                # Reset selection only on successful movement
                self.selected_model_index = None
                self.awaiting_battlefield_click = False
        else:
            # On failure, keep the model selected and continue waiting for battlefield clicks
            fail_word = 'Deployment' if self.movement_type == 'deploy' else 'Movement'
            print(f"❌ {fail_word} failed for {self.unit.models[self.selected_model_index].name}")
            print(f"🔄 Model remains selected. Try clicking on a valid location.")
        
        return success

    def _finalize_deploy_click_with_z(self, x: float, y: float, z: float) -> None:
        """Finalize a pending battlefield click after floor selection by DEPLOYING the model with chosen Z."""
        if self.selected_model_index is None:
            return
        model = self.unit.models[self.selected_model_index]

        # Validate single model deployment
        try:
            game = model.parent_unit.get_parent_army().player.game
        except Exception:
            game = None
        if not game:
            print("❌ Deployment failed: game context unavailable")
            return

        # Determine player by unit ownership
        try:
            player_name = model.parent_unit.get_parent_army().player.name
        except Exception:
            player_name = ''

        validation = self._validate_deploy_like_placement(game, model, x, y, z, player_name)
        if not validation['valid']:
            try:
                facing_deg = math.degrees(self.get_deploy_facing_radians())
            except Exception:
                facing_deg = 0.0
            print(
                f"❌ Deployment invalid for {model.name} at "
                f"({float(x):.1f}, {float(y):.1f}, {float(z):.1f}) facing={facing_deg:.1f}°: "
                f"{validation['reason']}"
            )
            return

        # Prevent illegal base overlaps during deployment.
        overlap_validation = self._validate_deployment_no_base_overlap(
            model=model,
            x=x,
            y=y,
            z=z,
            facing=self.get_deploy_facing_radians(),
        )
        if not overlap_validation['valid']:
            try:
                facing_deg = math.degrees(self.get_deploy_facing_radians())
            except Exception:
                facing_deg = 0.0
            print(
                f"❌ Deployment invalid for {model.name} at "
                f"({float(x):.1f}, {float(y):.1f}, {float(z):.1f}) facing={facing_deg:.1f}°: "
                f"{overlap_validation['reason']}"
            )
            return

        # Place the model at destination (preserve facing)
        current_facing = self.get_deploy_facing_radians()
        model.set_location(float(x), float(y), float(z), float(current_facing))
        print(f"✅ {model.name} deployed to ({float(x):.1f}, {float(y):.1f}{'' if abs(float(z)) < 1e-6 else f', {float(z):.1f}'})")

        # Mark model as deployed
        self.model_movements[self.selected_model_index] = {
            'path': [],
            'completed': True
        }

        # In deploy mode, immediately advance to the next unplaced alive model
        next_idx = None
        for idx, m in enumerate(self.unit.models):
            if not getattr(m, 'is_alive', True):
                continue
            if idx in self.model_movements and self.model_movements[idx].get('completed', False):
                continue
            next_idx = idx
            break

        if next_idx is not None:
            self._select_model(next_idx)
        else:
            self.selected_model_index = None
            self.awaiting_battlefield_click = False

    def _validate_deploy_like_placement(self, game, model, x: float, y: float, z: float, player_name: str) -> dict:
        """Validate deployment or custom placement for a single model."""
        if callable(self.placement_validator):
            try:
                return self.placement_validator(model, x, y, z)
            except Exception:
                return {"valid": False, "reason": "Custom placement validation failed"}
        try:
            return game.is_valid_single_model_deployment(model, x, y, z, player_name)
        except Exception:
            return {"valid": False, "reason": "Deployment validation failed"}

    def _validate_deployment_no_base_overlap(self, model, x: float, y: float, z: float, facing: Optional[float] = None) -> dict:
        """Ensure deployment placement doesn't overlap any model bases.

        Allows base-to-base contact (touching). Disallows overlap area > 0 on the same Z band.
        """
        try:
            from ...utility.model_base import Base as _Base
        except Exception:
            _Base = None

        if _Base is None:
            # If we can't construct temp bases, fall back to letting placement through
            return {'valid': True, 'reason': 'No overlap checker available'}

        # Build a temporary base at the destination so we can test overlap without mutating the model
        try:
            src_base = model.model_base
            cand = _Base(src_base.base_type, src_base.radius)
            cand.set_position(float(x), float(y), float(z))
            cand.set_facing(float(facing) if facing is not None else float(getattr(src_base, 'facing', 0.0)))
            # Preserve model height (important for 3D stacking edge-cases)
            try:
                cand.set_model_height(float(getattr(src_base, 'model_height', cand.model_height)))
            except Exception:
                pass
        except Exception:
            return {'valid': True, 'reason': 'No overlap checker available'}

        def _overlaps_3d(a, b, eps_area: float = 1e-6) -> bool:
            try:
                return bases_overlap_3d(a, b, eps_area=eps_area)
            except Exception:
                return False

        # 1) Check against already-placed models in the same unit (based on model_movements completed flags)
        try:
            placed_indices = {
                idx for idx, data in (self.model_movements or {}).items()
                if data.get('completed', False)
            }
        except Exception:
            placed_indices = set()

        for idx in placed_indices:
            try:
                other = self.unit.models[idx]
                if other is model or not getattr(other, 'is_alive', True):
                    continue
                if _overlaps_3d(cand, other.model_base):
                    return {'valid': False, 'reason': f"Overlaps base with {other.name} (same unit)"}
            except Exception:
                continue

        # 2) Check against all deployed units already registered on the map
        try:
            for u in getattr(self.game_map, 'units', []) or []:
                # Skip units not on the battlefield
                if not getattr(u, 'deployed', False):
                    continue
                for other in getattr(u, 'models', []) or []:
                    if other is model or not getattr(other, 'is_alive', True):
                        continue
                    # If this unit is already registered, we still only want to compare against
                    # models that have actually been placed for this unit.
                    if u is self.unit:
                        try:
                            other_idx = self.unit.models.index(other)
                        except Exception:
                            other_idx = None
                        if other_idx is not None and other_idx not in placed_indices:
                            continue
                    if _overlaps_3d(cand, other.model_base):
                        return {'valid': False, 'reason': f"Overlaps base with {other.name} ({u.name})"}
        except Exception:
            pass

        return {'valid': True, 'reason': 'No base overlap'}

    def _finalize_click_with_z(self, x: float, y: float, z: float) -> None:
        """Finalize a pending battlefield click after floor selection by moving the model with chosen Z."""
        destination = (x, y, z)
        success = self._move_model(self.selected_model_index, destination)
        if success:
            # Mark model as moved
            self.model_movements[self.selected_model_index] = {
                'path': [],
                'completed': True
            }
            # Reset selection only on successful movement
            self.selected_model_index = None
            self.awaiting_battlefield_click = False
        else:
            print(f"❌ Movement failed after floor selection for {self.unit.models[self.selected_model_index].name}")

    def _get_ruins_floor_options_for_model_at_xy(self, model, x: float, y: float) -> tuple[list[int], dict[int, float], list[int]]:
        """Return RUINS floor options for this model's BASE at XY.

        Returns:
        - levels: all floor levels (0,1,2,...) defined for the RUINS that contains the base
        - z_by_level: mapping level -> representative Z used for validation/movement
        - disabled_levels: subset of levels that are NOT valid at this XY for this model

        Notes:
        - Uses BASE geometry (not just the click point).
        - Requires the base to be wholly within the RUINS footprint to be considered "inside".
        - Validity per floor is decided by RUINS placement validation (overhang, unit restrictions, walls, clearance).
        """
        levels: list[int] = []
        z_by_level: dict[int, float] = {}
        disabled_levels: list[int] = []
        if not self.game_map:
            return levels, z_by_level, disabled_levels

        try:
            from shapely.geometry import Point as _ShPoint
        except Exception:
            _ShPoint = None

        # Compute base geometry at XY to enforce "wholly within"
        base_geom = None
        try:
            base_geom = model.model_base.get_base_shape_at(float(x), float(y), float(getattr(model.model_base, 'facing', 0.0)))
        except Exception:
            base_geom = None

        from warhammer40k_ai.battlefield.map import validate_ruins_placement

        for terrain in getattr(self.game_map, 'terrain_features', []) or []:
            try:
                ttype = getattr(terrain, 'terrain_type', None)
                if not ttype or getattr(ttype, 'name', '') != 'RUINS':
                    continue
                footprint = getattr(terrain, 'footprint', None)
                if footprint is None:
                    continue

                # Require base wholly within footprint when possible (allow touching boundary)
                if base_geom is not None:
                    try:
                        if hasattr(footprint, "covers"):
                            if not footprint.covers(base_geom):
                                continue
                        else:
                            if not footprint.contains(base_geom):
                                continue
                    except Exception:
                        continue
                else:
                    # Require point inside footprint.
                    if _ShPoint is None:
                        continue
                    try:
                        if not footprint.contains(_ShPoint(float(x), float(y))):
                            continue
                    except Exception:
                        continue

                # Collect candidate levels from floors definition
                candidate_levels: set[int] = set()
                for fl in getattr(terrain, 'floors', []) or []:
                    elev = float(fl.get('elevation', 0.0))
                    lvl = int(round(elev / float(RUINS_FLOOR_HEIGHT)))
                    candidate_levels.add(lvl)
                if not candidate_levels:
                    candidate_levels = {0}

                # We'll show all levels, but disable ones that aren't valid here
                levels = sorted(candidate_levels)
                for lvl in levels:
                    z = float(lvl) * float(RUINS_FLOOR_HEIGHT)
                    z_by_level[lvl] = z
                    res = validate_ruins_placement(
                        unit=self.unit,
                        position=(float(x), float(y), float(z)),
                        terrain_features=[terrain],
                        moving_model=model,
                    )
                    if not (res.get('valid') and int(res.get('floor_level', lvl)) == int(lvl)):
                        disabled_levels.append(lvl)

                # Only prompt for the first RUINS piece containing the base
                break
            except Exception:
                continue

        # If nothing is valid, avoid prompting (let normal placement validation handle it)
        if levels and len(disabled_levels) == len(levels):
            return [], {}, []

        return levels, z_by_level, disabled_levels
        
    def _move_model(self, model_index: int, destination) -> bool:
        """Move a specific model to the destination"""
        if model_index >= len(self.unit.models):
            print(f"❌ Invalid model index: {model_index}")
            return False
            
        model = self.unit.models[model_index]
        
        # Use unified pathfinding for ALL movement types
        #print(f"🔍 DEBUG: Using unified pathfinding for {model.name} with movement type {self.movement_type}")
        from ...utility.calcs import unified_pathfinding, MovementType

        # Get set of already-moved models (by object identity).
        # This works for both normal units and Attached units (where dialog uses a combined models list).
        moved_models_in_unit = set()
        for moved_index, movement_data in (self.model_movements or {}).items():
            try:
                if not movement_data.get('completed', False):
                    continue
                if 0 <= int(moved_index) < len(self.unit.models):
                    moved_models_in_unit.add(self.unit.models[int(moved_index)])
            except Exception:
                continue

        # Convert 2D target to 3D if needed
        if len(destination) == 2:
            target_3d = (destination[0], destination[1], model.model_base.z)
        else:
            target_3d = destination

        # Map movement type to MovementType enum for pathfinding
        movement_type_map = {
            'move': MovementType.MOVE,
            'advance': MovementType.ADVANCE,
            'fall_back': MovementType.FALL_BACK,
            'charge': MovementType.CHARGE,
            'blood_surge': MovementType.BLOOD_SURGE,
            'scout': MovementType.SCOUT,
            'pile_in': MovementType.PILE_IN,
            'consolidate': MovementType.CONSOLIDATE,
            'reactive': MovementType.MOVE,
            'loping_speed': MovementType.MOVE
        }

        pathfinding_movement_type = movement_type_map.get(self.movement_type, MovementType.MOVE)
        #print(f"🔍 DEBUG: Mapped {self.movement_type} to {pathfinding_movement_type}")

        path_result = unified_pathfinding(
            model=model,
            target=target_3d,
            movement_type=pathfinding_movement_type,
            max_distance=self.max_distance,
            game_map=self.game_map,
            target_unit=self.target_unit,
            moved_models_in_unit=moved_models_in_unit
        )

        #print(f"🔍 DEBUG: Pathfinding result for {model.name} to {destination}")
        #print(f"🔍 DEBUG: Path valid: {path_result['valid']}, movement_type: {pathfinding_movement_type}")
        #print(f"🔍 DEBUG: Reason: {path_result['reason']}")
        #if path_result['path']:
        #    print(f"🔍 DEBUG: Path length: {len(path_result['path'])}")

        if not path_result['valid'] or not path_result['path']:
            print(f"❌ No valid path found for {model.name} (Model #{model_index + 1})")
            print(f"   Reason: {path_result['reason']}")
            print(f"   Try clicking closer or on a clear area")
            return False

        # Convert 2D path back to 3D for movement
        path_3d = [(p[0], p[1], destination[2]) for p in path_result['path']]

        # Move the model along the path
        final_position = path_3d[-1]
        
        # Debug: Log current and target positions
        current_pos = model.get_location()
        #print(f"🔍 DEBUG: Model {model.name} current position: ({current_pos[0]:.2f}, {current_pos[1]:.2f}, {current_pos[2]:.2f})")
        #print(f"🔍 DEBUG: Target final position: ({final_position[0]:.2f}, {final_position[1]:.2f}, {final_position[2]:.2f})")
        
        # Update model position (preserve current facing)
        current_facing = model.model_base.facing if hasattr(model.model_base, 'facing') else 0.0
        model.set_location(final_position[0], final_position[1], final_position[2], current_facing)
        
        # Debug: Verify position was actually updated
        #new_pos = model.get_location()
        #print(f"🔍 DEBUG: Model {model.name} position after set_location: ({new_pos[0]:.2f}, {new_pos[1]:.2f}, {new_pos[2]:.2f})")
        
        # Store the movement path
        model.last_move_path = path_3d
        
        # Unit position is now determined by model positions
        
        print(f"✅ {model.name} (Model #{model_index + 1}) moved from ({current_pos[0]:.1f}, {current_pos[1]:.1f}, {current_pos[2]:.1f}) to ({final_position[0]:.1f}, {final_position[1]:.1f}, {final_position[2]:.1f})")
        try:
            from ...utility.event_bus import append_action
            pn = model.parent_unit.get_parent_army().player.name
            append_action(pn, f"{model.name} moved to ({final_position[0]:.1f}, {final_position[1]:.1f}), {final_position[2]:.1f}")
        except Exception:
            pass
        return True
    
    def _is_model_in_base_contact(self, model) -> bool:
        """Check if model is already in base-to-base contact with an enemy model"""
        from ...utility.constants import BASE_CONTACT_EPSILON
        
        if not self.game_map:
            return False
            
        for unit in self.game_map.units:
            if unit.faction == model.parent_unit.faction or not unit.is_alive() or not unit.deployed:
                continue
            for enemy_model in unit.models:
                if not enemy_model.is_alive:
                    continue
                    
                # Check 2D base contact (engagement uses its own special-case; base contact here is purely edge-to-edge in XY)
                from ...utility.aura_utils import horizontal_distance_between_bases_2d
                distance = float(horizontal_distance_between_bases_2d(model.model_base, enemy_model.model_base))
                if distance <= BASE_CONTACT_EPSILON:
                    print(f"🔍 DEBUG: {model.name} already in base contact with {enemy_model.name} (distance: {distance:.3f}\")")
                    return True
        
        return False
        
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

        # During deployment, require every alive model to be placed before completing
        if self.movement_type == 'deploy' and not self._all_models_moved():
            remaining_models = [
                idx + 1
                for idx, model in enumerate(self.unit.models)
                if model.is_alive and (
                    idx not in self.model_movements
                    or not self.model_movements[idx]['completed']
                )
            ]
            print(f"⚠️  Cannot complete deployment: models {remaining_models} still need placement")
            return

        # Validate unit coherency
        from ...utility.calcs import validate_unit_coherency_after_movement

        # Get final positions of all models
        final_positions = []
        for model in self.unit.models:
            final_positions.append(model.get_location())

        is_coherent, non_coherent_models = validate_unit_coherency_after_movement(self.unit, final_positions)

        if not is_coherent:
            # Movement/deployment must END in coherency. If coherency would be broken, the move is not allowed.
            print(f"❌ Cannot complete {self.movement_type}: {self.unit.name} would not be in coherency "
                  f"(non-coherent models: {non_coherent_models}). Reposition models and try again.")
            return
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
        print(f"✅ {self.unit.name} {self.movement_type.upper()} movement completed")

        # Set unit round state based on movement type
        # NOTE: Scout movement happens before battle rounds, so it should NOT set round state flags
        # For Attached units, apply to all member units (bodyguard + leaders), not just the proxy/root.
        try:
            units_to_update = list(self._attached_members or [])
        except Exception:
            units_to_update = []
        if not units_to_update:
            units_to_update = [self.unit]

        for u in units_to_update:
            try:
                if self.movement_type == 'advance':
                    u.round_state.advanced_this_round = True
                elif self.movement_type == 'fall_back':
                    u.round_state.fell_back_this_round = True
                elif self.movement_type in ['move', 'pile_in', 'consolidate', 'charge']:
                    u.round_state.moved_this_round = True
                    u.round_state.remained_stationary_this_round = False
            except Exception:
                continue
        # Scout movement does not set round state flags since it happens pre-battle

        # Publish unit move ended (for Stratagem reactions like Overwatch)
        # NOTE: Do NOT publish for deployment placement.
        if self.movement_type not in ('deploy', 'reactive', 'blood_surge', 'loping_speed'):
            try:
                _player = getattr(self.unit.get_parent_army(), 'player', None)
                _game = getattr(_player, 'game', None) if _player else None
                if _game and hasattr(_game, 'event_system'):
                    action = 'move'
                    if self.movement_type == 'advance':
                        action = 'advance'
                    elif self.movement_type == 'fall_back':
                        action = 'fall_back'
                    elif self.movement_type == 'charge':
                        action = 'charge'
                    _game.event_system.publish("unit_move_ended", unit=self.unit, action=action)
            except Exception:
                pass
        if self.movement_type == 'reactive':
            self._clear_battle_focus_reactive_flags()

        # Call callback with completion status
        if self.callback:
            self.callback(True)  # Movement completed

        self.hide()
        
    def _skip_movement(self):
        """Skip movement for this unit"""
        print(f"⏭️  Skipping {self.movement_type} movement for {self.unit.name}")
        if self.movement_type == "reactive":
            self._clear_battle_focus_reactive_flags()

        # Call callback with skip status
        if self.callback:
            self.callback(False)  # Movement skipped

        self.hide()

    def _clear_battle_focus_reactive_flags(self) -> None:
        try:
            units_to_update = list(self._attached_members or [])
        except Exception:
            units_to_update = []
        if not units_to_update:
            units_to_update = [self.unit]
        for u in units_to_update:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for k in (
                "battle_focus_reactive_move_max",
                "battle_focus_reactive_move_source",
                "battle_focus_reactive_move_expires_phase",
            ):
                sr.pop(k, None)
        
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
            if button.get('disabled', False):
                button_color = (40, 40, 40)  # BUTTON_DISABLED - dark gray
                text_color = (100, 100, 100)  # TEXT_DISABLED - dim gray
            elif model_index == self.selected_model_index:
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
            if button.get('disabled', False):
                model_name += f" ({button.get('disabled_reason', 'Unavailable')})"
            elif model_index in self.model_movements and self.model_movements[model_index]['completed']:
                # No extra marker needed; color already indicates completion
                pass
            elif not model.is_alive:
                model_name += " (Dead)"

            # Fit label to button width
            padding_x = 6
            fitted = self._truncate_middle_preserve_suffix(model_name, self.font_small, rect.width - (padding_x * 2))
            text_surface = self.font_small.render(fitted, True, text_color)
            text_rect = text_surface.get_rect()
            text_rect.midleft = (rect.left + padding_x, rect.centery)
            screen.blit(text_surface, text_rect)
            
        # Draw instructions
        if self.awaiting_battlefield_click:
            instruction_text = f"Click on battlefield to move #{self.selected_model_index + 1}: {self.unit.models[self.selected_model_index].name}"
            if getattr(self, "movement_type", "") == "deploy":
                instruction_text += " | Mouse wheel: rotate facing (5°)"
            instruction_color = TEXT_WARNING
        else:
            instruction_text = "Select a model, then click on battlefield to move it. ESC to close."
            instruction_color = (200, 200, 200)  # TEXT_SECONDARY

        # Fit instructions to dialog width
        instr_fitted = self._truncate_middle_preserve_suffix(instruction_text, self.font_small, self.width - 40)
        instruction_surface = self.font_small.render(instr_fitted, True, instruction_color)
        screen.blit(instruction_surface, (self.x + 20, self.y + self.height - 80))
        
        # Draw control buttons using base class method
        self.draw_button(screen, 'complete', "Complete")
        self.draw_button(screen, 'skip', "Skip")

        # Draw coherency dialog if it's open
        if hasattr(self, 'coherency_dialog') and self.coherency_dialog.visible:
            self.coherency_dialog.draw(screen)
        # Draw floor selection dialog if it's open
        if hasattr(self, 'floor_selection_dialog') and self.floor_selection_dialog and self.floor_selection_dialog.visible:
            self.floor_selection_dialog.draw(screen)
