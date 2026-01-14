"""
Melee Weapon Declaration Dialog for Warhammer 40k AI

Refactored to use BaseDialog for consistent UI (title bar, drag, buttons), fixed
overlapping labels, and improved layout clarity.
"""

import pygame
from typing import List, Dict, Optional, Callable
from ...classes.unit import Unit
from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY

# Enhanced Colors
PANEL_BG = (50, 50, 50)
PANEL_BORDER = (100, 100, 100)
BUTTON_BG = (70, 70, 70)
BUTTON_HOVER = (100, 100, 100)
BUTTON_SELECTED = (120, 120, 120)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (255, 100, 100)  # Red accent color for melee combat
MELEE_COLOR = (255, 100, 100)  # Red for melee weapons
EXTRA_ATTACKS_COLOR = (255, 200, 100)  # Orange for extra attacks

class MeleeWeaponDeclarationDialog(BaseDialog):
    """
    Melee weapon declaration dialog that allows players to declare melee weapons
    and targets before executing all melee attacks simultaneously.
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=800, height=600, draggable=True, center=True)
        
        # Unit and callback
        self.unit = None
        self.callback = None
        self.game_map = None
        self.target_unit = None
        self.eligible_models = None
        
        # Model-based weapon declarations storage
        self.model_weapon_selections = {}  # {model_index: {weapon_profile_id: weapon_info}}
        self.available_weapons_by_model = {}  # {model_index: [weapon_list]}
        
        # UI state
        self.weapon_buttons = []
        self.scroll_offset = 0
        self.max_scroll = 0
        self.selected_model_index = None  # Currently selected model for weapon assignment
        
        # Weapon group expansion state
        self.expanded_weapon_groups = set()  # Set of weapon profile IDs that are expanded
        
        # Colors
        self.bg_color = (50, 50, 50, 230)
        self.border_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.button_color = (80, 80, 80)
        self.button_hover_color = (120, 120, 120)
        self.selected_color = (120, 120, 120)
        
        # Fonts provided by BaseDialog: self.font_large/medium/small
    
    def show(self, unit: Unit, callback: Callable, game_map=None, target_unit=None):
        """Show the melee weapon declaration dialog."""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.target_unit = target_unit
        # Preserve callback in BaseDialog for button handling
        super().show(callback)
        
        # Initialize weapon selection
        self._initialize_weapon_selection()
        
        print(f"⚔️ MeleeWeaponDeclarationDialog shown for {unit.name}")
    
    def hide(self):
        """Hide the dialog."""
        super().hide()
        self.unit = None
        self.callback = None
        self.game_map = None
        self.target_unit = None
        self.eligible_models = None
        self.model_weapon_selections = {}
        self.available_weapons_by_model = {}
        self.weapon_buttons = []
        self.selected_model_index = None
        self.expanded_weapon_groups.clear()  # Clear expansion state
    
    def _initialize_weapon_selection(self):
        """Initialize the model-based weapon selection interface."""
        self.weapon_buttons = []
        self.model_weapon_selections = {}
        self.available_weapons_by_model = {}
        self.eligible_models = None
        
        if not self.unit:
            return
        
        print(f"🔍 DEBUG: Initializing weapon selection for {self.unit.name}")
        print(f"🔍 DEBUG: Unit has {len(self.unit.models)} models")
        
        if (
            self.target_unit is not None
            and self.game_map is not None
            and hasattr(self.unit, "has_fight_within_3_ability")
            and self.unit.has_fight_within_3_ability()
        ):
            try:
                self.eligible_models = set(
                    self.unit.get_fight_eligible_models_for_target(
                        self.target_unit,
                        game_map=self.game_map,
                        allow_within_3=self.unit.fight_within_3_active(),
                    )
                )
            except Exception:
                self.eligible_models = None

        eligible_indices = []
        # Initialize weapon selections for each model
        for model_index, model in enumerate(self.unit.models):
            if not model.is_alive:
                continue
            if self.eligible_models is not None and model not in self.eligible_models:
                continue
            eligible_indices.append(model_index)
                
            # Get available weapons for this model
            model_weapons = self._get_available_melee_weapons_for_model(model)
            self.available_weapons_by_model[model_index] = model_weapons
            
            # Initialize with default selections (primary weapon + all extra attack weapons)
            self.model_weapon_selections[model_index] = {}
            primary_selected = False
            
            for weapon_info in model_weapons:
                profile = weapon_info['profile']
                profile_id = id(profile)
                has_extra_attacks = profile.is_extra_attacks()
                
                if has_extra_attacks:
                    # Always auto-select extra attack weapons
                    self.model_weapon_selections[model_index][profile_id] = weapon_info
                elif not has_extra_attacks and not primary_selected:
                    # Select first primary weapon found
                    self.model_weapon_selections[model_index][profile_id] = weapon_info
                    primary_selected = True
        
        # Set first eligible model as selected by default
        self.selected_model_index = eligible_indices[0] if eligible_indices else None
        self._create_model_and_weapon_buttons()
        
    def _get_available_melee_weapons_for_model(self, model):
        """Get all available melee weapon profiles for a specific model."""
        weapons = []
        
        if not model.is_alive:
            return weapons
        
        for wargear in model.wargear:
            if wargear.is_melee():
                for profile_name, profile in wargear.profiles.items():
                    weapons.append({
                        'profile': profile,
                        'wargear': wargear,
                        'profile_name': profile_name,
                        'model': model
                    })
        
        return weapons
        
    def _create_model_and_weapon_buttons(self):
        """Create buttons for model selection and weapon selection."""
        self.weapon_buttons = []
        
        # Model selection area (top section)
        model_section_height = 100
        y_offset = 80
        
        # Model buttons - horizontal layout
        models_per_row = 4
        button_width = (self.width - 60) // models_per_row  # Leave margins
        button_height = 30
        
        model_button_y = y_offset + 20
        for model_index, model in enumerate(self.unit.models):
            if not model.is_alive:
                continue
            if self.eligible_models is not None and model not in self.eligible_models:
                continue
                
            col = model_index % models_per_row
            row = model_index // models_per_row
            
            button_x = 20 + col * button_width
            button_y = model_button_y + row * (button_height + 5)
            
            button_rect = pygame.Rect(button_x, button_y, button_width - 5, button_height)
            
            self.weapon_buttons.append({
                'type': 'model',
                'rect': button_rect,
                'model_index': model_index,
                'model': model,
                'selected': model_index == self.selected_model_index
            })
        
        # Weapon selection area (bottom section)
        weapon_section_start = y_offset + model_section_height
        
        if self.selected_model_index is not None and self.selected_model_index in self.available_weapons_by_model:
            weapons = self.available_weapons_by_model[self.selected_model_index]
            weapon_button_height = 60
            
            for i, weapon_info in enumerate(weapons):
                button_y = weapon_section_start + i * weapon_button_height
                button_rect = pygame.Rect(20, button_y, self.width - 40, weapon_button_height - 5)
                
                profile = weapon_info['profile']
                profile_id = id(profile)
                has_extra_attacks = profile.is_extra_attacks()
                
                # Check if this weapon is selected for the current model
                is_selected = (self.selected_model_index in self.model_weapon_selections and 
                             profile_id in self.model_weapon_selections[self.selected_model_index])
                
                self.weapon_buttons.append({
                    'type': 'weapon',
                    'rect': button_rect,
                    'weapon_info': weapon_info,
                    'selected': is_selected,
                    'has_extra_attacks': has_extra_attacks,
                    'profile_id': profile_id
                })
        
        # Calculate scroll limits
        total_height = weapon_section_start
        if self.selected_model_index is not None:
            total_height += len(self.available_weapons_by_model.get(self.selected_model_index, [])) * 60
        content_height = self.height - 160  # Leave space for title and execute button
        self.max_scroll = max(0, total_height - content_height)
    

    
    def handle_event(self, event):
        """Handle pygame events."""
        if not self.visible:
            return False
        # Base handling for drag/title/buttons
        if super().handle_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = pygame.mouse.get_pos()
                if self._is_click_in_dialog(mouse_pos):
                    self._handle_click(mouse_pos)
                    return True
            elif event.button == 4:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 20)
                return True
            elif event.button == 5:  # Scroll down
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            elif event.key == pygame.K_RETURN:
                self._execute_attacks()
                return True
        
        return False
    
    def _handle_click(self, mouse_pos):
        """Handle mouse clicks."""
        x, y = mouse_pos
        dialog_x = x - self.x
        dialog_y = y - self.y
        
        # Check button clicks
        for button in self.weapon_buttons:
            adjusted_rect = pygame.Rect(
                button['rect'].x,
                button['rect'].y - self.scroll_offset,
                button['rect'].width,
                button['rect'].height
            )
            if adjusted_rect.collidepoint(dialog_x, dialog_y):
                button_type = button.get('type', 'weapon')
                
                if button_type == 'model':
                    # Model selection
                    model_index = button['model_index']
                    if model_index != self.selected_model_index:
                        self.selected_model_index = model_index
                        print(f"🎯 Selected Model #{model_index + 1}: {button['model'].name}")
                        self._create_model_and_weapon_buttons()  # Refresh UI
                    return True
                    
                elif button_type == 'weapon':
                    # Weapon selection for the current model
                    if self.selected_model_index is None:
                        return True
                        
                    weapon_info = button['weapon_info']
                    profile_id = button['profile_id']
                    has_extra_attacks = button.get('has_extra_attacks', False)
                    
                    if self.selected_model_index not in self.model_weapon_selections:
                        self.model_weapon_selections[self.selected_model_index] = {}
                    
                    current_selections = self.model_weapon_selections[self.selected_model_index]
                    
                    if button['selected']:
                        # Deselecting a weapon
                        if has_extra_attacks:
                            # Can always deselect extra attack weapons
                            if profile_id in current_selections:
                                del current_selections[profile_id]
                        else:
                            # Deselecting primary weapon - only allowed if another primary is selected
                            other_primary_selected = any(
                                pid for pid, winfo in current_selections.items() 
                                if not winfo['profile'].is_extra_attacks() and pid != profile_id
                            )
                            if other_primary_selected:
                                if profile_id in current_selections:
                                    del current_selections[profile_id]
                            # If no other primary selected, don't allow deselection
                    else:
                        # Selecting a weapon
                        if has_extra_attacks:
                            # Can always select extra attack weapons
                            current_selections[profile_id] = weapon_info
                        else:
                            # Selecting primary weapon - deselect other primary weapons first
                            primary_weapons_to_remove = [
                                pid for pid, winfo in current_selections.items() 
                                if not winfo['profile'].is_extra_attacks()
                            ]
                            for pid in primary_weapons_to_remove:
                                del current_selections[pid]
                            
                            current_selections[profile_id] = weapon_info
                    
                    # Refresh the weapon buttons to update selection state
                    self._create_model_and_weapon_buttons()
                    return True
        
        # Check execute button
        execute_button_rect = pygame.Rect(20, self.height - 60, self.width - 40, 40)
        if execute_button_rect.collidepoint(dialog_x, dialog_y):
            self._execute_attacks()
    
    def _execute_attacks(self):
        """Execute the declared melee attacks."""
        if self.callback:
            # Convert model-based selections to weapon declarations format
            weapon_declarations = []
            
            for model_index, weapon_selections in self.model_weapon_selections.items():
                if model_index >= len(self.unit.models):
                    continue
                    
                model = self.unit.models[model_index]
                if not model.is_alive:
                    continue
                
                # Each model should have exactly one weapon selected (primary + any extra attacks)
                for profile_id, weapon_info in weapon_selections.items():
                    weapon_declarations.append({
                        'model': model,
                        'weapon_profile': weapon_info['profile'],
                        'wargear': weapon_info['wargear'],
                        'profile_name': weapon_info.get('profile_name', 'default')
                    })
            
            # Validate that each alive model has at least one weapon selected
            total_models = len([m for m in self.unit.models if m.is_alive])
            models_with_weapons = len(self.model_weapon_selections)
            
            if models_with_weapons < total_models:
                print(f"⚠️ Warning: Only {models_with_weapons}/{total_models} models have weapon selections")
                print(f"⚠️ Some models may not be able to attack")
            
            print(f"⚔️ Weapon selection completed with {len(weapon_declarations)} weapon declarations")
            print(f"⚔️ Covering {models_with_weapons}/{total_models} models")
            self.callback(weapon_declarations)
        self.hide()
    
    def _is_click_in_dialog(self, mouse_pos):
        """Check if click is within dialog bounds."""
        x, y = mouse_pos
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)
    
    def draw(self, screen):
        """Draw the dialog."""
        if not self.visible:
            return
        # Dialog background and title bar
        self.draw_dialog_background(screen)
        title = f"Melee Weapons - {self.unit.name if self.unit else 'Unknown'}"
        self.draw_title_bar(screen, title, subtitle="Select a model, then its melee weapons")

        # Draw content directly on screen for simplicity
        self._draw_weapon_buttons(screen)

        # Execute button
        self.add_button("execute", 20, self.height - 60, self.width - 40, 40, enabled=True)
        # Choose color based on readiness
        total_declarations = sum(len(selections) for selections in self.model_weapon_selections.values())
        models_ready = len(self.model_weapon_selections)
        total_models = len([m for m in self.unit.models if m.is_alive]) if self.unit else 0
        btn_label = f"Execute Melee Attacks ({models_ready}/{total_models} models ready)"
        # Draw button with default style; color hint via text
        self.draw_button(screen, "execute", btn_label)
    
    def _draw_weapon_buttons(self, surface):
        """Draw the model selection and weapon selection buttons."""
        # Create clipping area for scrolling (below title bar)
        clip_rect = pygame.Rect(self.x + 20, self.y + self.title_bar_height + 10, self.width - 40, self.height - self.title_bar_height - 80)
        
        for button in self.weapon_buttons:
            # Calculate position with scroll offset
            button_rect = pygame.Rect(
                self.x + button['rect'].x,
                self.y + button['rect'].y - self.scroll_offset,
                button['rect'].width,
                button['rect'].height
            )
            
            # Skip if button is outside visible area
            if (button_rect.bottom < clip_rect.top or button_rect.top > clip_rect.bottom):
                continue
            
            button_type = button.get('type', 'weapon')
            
            if button_type == 'model':
                # Draw model selection button
                model = button['model']
                model_index = button['model_index']
                is_selected = button['selected']
                
                # Check if model has weapons selected
                has_weapons = model_index in self.model_weapon_selections and len(self.model_weapon_selections[model_index]) > 0
                
                if is_selected:
                    button_color = BUTTON_SELECTED
                elif has_weapons:
                    button_color = (100, 150, 100)  # Green for models with weapons
                else:
                    button_color = self.button_color
                
                pygame.draw.rect(surface, button_color, button_rect)
                pygame.draw.rect(surface, self.border_color, button_rect, 1)
                
                # Model name and status
                model_text = f"#{model_index + 1}: {model.name}"
                if has_weapons:
                    weapon_count = len(self.model_weapon_selections[model_index])
                    model_text += f" ({weapon_count})"
                
                name_surface = self.font_small.render(model_text, True, TEXT_PRIMARY)
                text_rect = name_surface.get_rect(center=button_rect.center)
                surface.blit(name_surface, text_rect)
                
            elif button_type == 'weapon':
                # Draw weapon selection button
                weapon_info = button['weapon_info']
                wargear = weapon_info['wargear']
                profile = weapon_info['profile']
                profile_name = weapon_info.get('profile_name', 'default')
                has_extra_attacks = button.get('has_extra_attacks', False)
                is_selected = button['selected']
                
                # Draw button background
                if is_selected:
                    # Use the same selected style as ranged dialog for readability
                    button_color = BUTTON_SELECTED
                else:
                    button_color = self.button_color
                
                pygame.draw.rect(surface, button_color, button_rect)
                pygame.draw.rect(surface, self.border_color, button_rect, 1)
                
                # Line 1: Weapon name
                weapon_name = wargear.name
                if profile_name != 'default':
                    weapon_name += f" - {profile_name}"
                
                # Add indicator for extra attacks weapons
                if has_extra_attacks:
                    weapon_name += " [EXTRA ATTACKS]"
                
                name_surface = self.font_medium.render(weapon_name, True, TEXT_PRIMARY)
                surface.blit(name_surface, (button_rect.x + 10, button_rect.y + 5))
                
                # Line 2: Weapon stats (melee format: A/WS/S/AP/D)
                stats_parts = []
                if hasattr(profile, 'attacks'):
                    stats_parts.append(f"A: {profile.attacks}")
                if hasattr(profile, 'skill'):
                    stats_parts.append(f"WS: {profile.skill}+")
                if hasattr(profile, 'strength'):
                    stats_parts.append(f"S: {profile.strength}")
                if hasattr(profile, 'ap'):
                    stats_parts.append(f"AP: {profile.ap}")
                if hasattr(profile, 'damage'):
                    stats_parts.append(f"D: {profile.damage}")
                
                if stats_parts:
                    stats_text = " | ".join(stats_parts)
                    stats_surface = self.font_small.render(stats_text, True, TEXT_SECONDARY)
                    surface.blit(stats_surface, (button_rect.x + 10, button_rect.y + 25))
                
                # Line 3: Keywords (if any) - use the same blue accent as ranged, on neutral/selected backgrounds
                keywords = profile.get_keywords() if hasattr(profile, 'get_keywords') else []
                if keywords:
                    keywords_text = ", ".join(keywords)
                    # Use blue accent like shooting dialog
                    keywords_surface = self.font_small.render(keywords_text, True, (100, 149, 237))
                    surface.blit(keywords_surface, (button_rect.x + 10, button_rect.y + 42))
                
                # Selection indicator
                if is_selected:
                    check_surface = self.font_medium.render("✓", True, TEXT_PRIMARY)
                    surface.blit(check_surface, (button_rect.right - 30, button_rect.y + 10))
                    
        # Draw section labels
        if self.unit:
            # Model selection label
            model_label = self.font_medium.render("Select Model:", True, TEXT_ACCENT)
            surface.blit(model_label, (self.x + 20, self.y + self.title_bar_height + 5))
            
            # Weapon selection label
            if self.selected_model_index is not None:
                model_name = self.unit.models[self.selected_model_index].name
                weapon_label = self.font_medium.render(f"Weapons for {model_name}:", True, TEXT_ACCENT)
                surface.blit(weapon_label, (self.x + 20, self.y + self.title_bar_height + 85))

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "execute":
            self._execute_attacks()
            return True
        return False
