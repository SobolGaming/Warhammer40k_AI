import pygame
from typing import List

# Enhanced Colors
PANEL_BG = (50, 50, 50)
PANEL_BORDER = (100, 100, 100)
BUTTON_BG = (70, 70, 70)
BUTTON_HOVER = (100, 100, 100)
BUTTON_SELECTED = (120, 120, 120)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (100, 149, 237)  # Blue accent color for keywords


class ShootingDeclarationDialog:
    """
    Advanced shooting declaration dialog that allows players to declare multiple weapons
    and targets before executing all shooting simultaneously.
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.width = 625  # Increased from 500 (25% wider)
        self.height = 600
        self.x = 50
        self.y = 50
        self.visible = False
        
        # Unit and callback
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        
        # Weapon selection and targeting state
        self.selected_weapon = None  # The currently selected weapon profile
        self.is_targeting_mode = False
        
        # Declarations storage
        self.weapon_declarations = []
        
        # UI state
        self.scroll_offset = 0
        self.max_scroll = 0
        self.hovered_weapon = -1
        
        # Colors
        self.text_color = (255, 255, 255)
        self.bg_color = (50, 50, 50, 230)
        self.border_color = (100, 100, 100)
        self.button_color = (80, 80, 80)
        self.button_hover_color = (120, 120, 120)
        self.selected_color = (0, 150, 255)
        self.valid_target_color = (0, 200, 0)
        self.invalid_target_color = (200, 0, 0)
        
        # Dialog state
        self.available_weapons = []
        self.available_targets = []
        self.selected_weapon_profile = None
        
        # Weapon group expansion state
        self.expanded_weapon_groups = set()  # Set of weapon profile IDs that are expanded
    
    def show(self, unit, callback, game_map=None, game_view=None):
        """Show the shooting declaration dialog."""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        self.game_view = game_view
        self.visible = True
        
        # Clear previous state
        self.weapon_declarations = []
        self.selected_weapon = None
        self.is_targeting_mode = False
        
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
        
        # Get available weapons and targets
        self.available_weapons = self._get_available_weapons()
        self.available_targets = self._get_available_targets()

        # Calculate initial max scroll
        self.max_scroll = self.get_max_scroll()

        print(f"🎯 ShootingDeclarationDialog shown for {unit.name}")
        print(f"🎯 Found {len(self.available_weapons)} available weapons")
        print(f"🎯 Found {len(self.available_targets)} available targets")
    
    def hide(self):
        """Hide the shooting declaration dialog."""
        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None

        # Clear weapon profile on game view to remove range visualization
        if hasattr(self, 'game_view') and self.game_view:
            self.game_view.selected_weapon_profile = None

        self.game_view = None
        self.weapon_declarations = []
        self.available_weapons = []
        self.available_targets = []
        self.selected_weapon = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self.is_targeting_mode = False
        self.expanded_weapon_groups.clear()  # Clear expansion state
    
    def _get_available_weapons(self):
        """Get all available weapon profiles for the unit, grouped by type."""
        # First, collect all individual weapons
        individual_weapons = []
        
        for model in self.unit.models:
            if not model.is_alive:
                continue
            
            for wargear in model.wargear:
                if wargear.is_ranged():
                    for profile_name, profile in wargear.profiles.items():
                        # Check if weapon can be used
                        if self._can_use_weapon(profile):
                            individual_weapons.append({
                                'profile': profile,
                                'wargear': wargear,
                                'profile_name': profile_name,
                                'model': model,
                                'weapon_instance': len([w for w in individual_weapons if w['profile'] == profile]) + 1
                            })
        
        # Group weapons by profile
        weapon_groups = {}
        for weapon in individual_weapons:
            profile_id = id(weapon['profile'])
            if profile_id not in weapon_groups:
                weapon_groups[profile_id] = {
                    'profile': weapon['profile'],
                    'wargear': weapon['wargear'],
                    'profile_name': weapon['profile_name'],
                    'individual_weapons': [],
                    'is_group': True
                }
            weapon_groups[profile_id]['individual_weapons'].append(weapon)
        
        # Build the final weapons list
        weapons = []
        for profile_id, group in weapon_groups.items():
            if len(group['individual_weapons']) == 1:
                # Single weapon - add as individual entry
                weapon = group['individual_weapons'][0]
                weapons.append({
                    'profile': weapon['profile'],
                    'wargear': weapon['wargear'],
                    'profile_name': weapon['profile_name'],
                    'models': [weapon['model']],
                    'weapon_instance': weapon['weapon_instance'],
                    'is_group': False,
                    'group_id': None
                })
            else:
                # Multiple weapons - add as group
                if profile_id in self.expanded_weapon_groups:
                    # Group is expanded - add individual weapons
                    for weapon in group['individual_weapons']:
                        weapons.append({
                            'profile': weapon['profile'],
                            'wargear': weapon['wargear'],
                            'profile_name': weapon['profile_name'],
                            'models': [weapon['model']],
                            'weapon_instance': weapon['weapon_instance'],
                            'is_group': False,
                            'group_id': profile_id
                        })
                else:
                    # Group is collapsed - add as single group entry
                    all_models = [w['model'] for w in group['individual_weapons']]
                    weapons.append({
                        'profile': group['profile'],
                        'wargear': group['wargear'],
                        'profile_name': group['profile_name'],
                        'models': all_models,
                        'count': len(group['individual_weapons']),
                        'is_group': True,
                        'group_id': profile_id,
                        'individual_weapons': group['individual_weapons']
                    })
        
        return weapons
    
    def _get_available_targets(self):
        """Get list of available target units."""
        if not self.game_map:
            return []
            
        # Get all enemy units
        enemy_units = self.game_map.get_enemy_units(self.unit)
        
        # Filter out dead units
        enemy_units = [unit for unit in enemy_units if unit.is_alive()]
        
        return enemy_units
    
    def _can_use_weapon(self, weapon_profile):
        """Check if a weapon can be used."""
        # Check if weapon has any shots
        if not weapon_profile.attacks:
            return False
            
        # Check if unit advanced this round and weapon allows shooting after advance
        if self.unit.round_state.advanced_this_round:
            # Unit method already checks both weapon-specific and unit-specific abilities
            if not self.unit.can_shoot_after_advance(weapon_profile):
                return False
        
        # Check if unit fell back this round and weapon allows shooting after falling back
        if self.unit.round_state.fell_back_this_round:
            if not self.unit.can_shoot_after_fall_back(weapon_profile):
                return False
        
        # Check if unit is in engagement range (can only shoot pistols or into melee)
        if not self.unit.can_shoot_in_engagement_range(self.game_map, weapon_profile):
            return False
        
        return True
    
    def _can_target_unit(self, weapon_profile, target_unit):
        """Check if a weapon can target a specific unit."""
        # Check range
        min_distance = float('inf')
        for shooting_model in self.unit.models:
            if not shooting_model.is_alive:
                continue
            for target_model in target_unit.models:
                if not target_model.is_alive:
                    continue
                # Calculate distance between model bases
                distance = shooting_model.model_base.edge_to_edge_distance(target_model.model_base)
                min_distance = min(min_distance, distance)
        
        if min_distance > weapon_profile.range.max:
            return False
        
        # Check line of sight (simplified)
        return True
    
    def _has_line_of_sight(self, shooting_model, target_model):
        """Check if shooting model has line of sight to target model."""
        # Simplified line of sight check
        return True
    
    def _get_models_with_weapon(self, weapon_profile):
        """Get all models in the unit that have this weapon."""
        models = []
        for model in self.unit.models:
            if model.is_alive:
                for wargear in model.wargear:
                    for profile_name, profile in wargear.profiles.items():
                        if profile == weapon_profile:
                            models.append(model)
                            break
        return models
    
    def handle_event(self, event):
        """Handle pygame events"""

        # If not visible and not in targeting mode, ignore all events
        if not self.visible and not self.is_targeting_mode:
            return False

        # If in targeting mode, only handle ESC key and let all other events pass through
        if self.is_targeting_mode:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                print("🎯 ESC pressed in targeting mode - clearing targeting")
                self.clear_targeting_mode()
                return True
            return False  # Let other handlers (like battle phase) handle targeting clicks
        
        # Normal dialog event handling when visible and not in targeting mode
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.handle_click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):  # Mouse wheel
            if event.button == 4:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 50)
            else:  # Scroll down
                self.scroll_offset = min(self.get_max_scroll(), self.scroll_offset + 50)
        
        return True  # Consume events when dialog is visible
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks in the dialog."""
        x, y = mouse_pos
        
        # Convert to dialog-relative coordinates
        relative_x = x - self.x
        relative_y = y - self.y
        
        # Check if click is outside dialog
        if relative_x < 0 or relative_x > self.width or relative_y < 0 or relative_y > self.height:
            # Click outside dialog
            if self.is_targeting_mode:
                print("🎯 [handle_click] Clearing targeting mode")
                self.clear_targeting_mode()
            else:
                self.hide()
            return True
        
        # Handle weapon selection clicks
        if self._handle_weapon_click(relative_x, relative_y):
            return True
        
        # Handle declaration list clicks (to remove declarations)
        if self._handle_declaration_click(relative_x, relative_y):
            return True
        
        # Handle button clicks
        if self._handle_button_click(relative_x, relative_y):
            return True
        
        return True
    
    def _handle_weapon_click(self, x, y):
        """Handle clicks on the weapons list."""
        weapon_list_x = 10
        weapon_list_y = 80
        weapon_list_height = self.height - 200  # Leave space for declarations and buttons
        
        if not (weapon_list_y <= y <= weapon_list_y + weapon_list_height):
            return False
        
        # Calculate which weapon was clicked
        relative_y = y - weapon_list_y + self.scroll_offset
        weapon_index = relative_y // 50  # 50 pixels per weapon
        
        available_weapons = self._get_available_weapons()
        if 0 <= weapon_index < len(available_weapons):
            weapon_info = available_weapons[weapon_index]
            weapon_profile = weapon_info['profile']
            
            # Check if this is a click on the expand/collapse button
            if weapon_info.get('is_group', False):
                # Check if click is on the expand/collapse button area (right side)
                button_x = self.width - 40  # 40 pixels from right edge
                if x >= button_x:
                    group_id = weapon_info['group_id']
                    self._toggle_weapon_group_expansion(group_id)
                    print(f"🔄 Toggled weapon group expansion for {weapon_profile.parent_wargear.name}")
                    return True
            
            # Handle individual weapon selection
            if not weapon_info.get('is_group', False):
                weapon_instance = weapon_info.get('weapon_instance', 1)
                
                # Check if weapon can be used and hasn't been declared already
                if self._can_use_weapon(weapon_profile) and not self._is_weapon_already_declared(weapon_profile.parent_wargear, weapon_instance):
                    print(f"🎯 Selected weapon: {weapon_profile.parent_wargear.name} #{weapon_instance}")
                    self.select_weapon_for_targeting(weapon_profile, weapon_instance)
                    return True
                else:
                    print(f"❌ Cannot use {weapon_profile.parent_wargear.name} #{weapon_instance} - already declared or unavailable")
            else:
                # Handle grouped weapon selection - all weapons in group target the same enemy
                if self._can_use_weapon(weapon_profile):
                    print(f"🎯 Selected weapon group: {weapon_profile.parent_wargear.name} (x{weapon_info['count']})")
                    self.select_weapon_group_for_targeting(weapon_info)
                    return True
                else:
                    print(f"❌ Cannot use weapon group {weapon_profile.parent_wargear.name} - unavailable")
        
        return False
    
    def _find_existing_declaration(self, weapon_profile, weapon_instance=1):
        """Find if a weapon profile is already declared"""
        for declaration in self.weapon_declarations:
            if (declaration['weapon_profile'] == weapon_profile and 
                declaration.get('weapon_instance', 1) == weapon_instance):
                return declaration
        return None
    
    def _is_weapon_already_declared(self, wargear, weapon_instance=1):
        """Check if a specific instance of this weapon has already been declared"""
        for declaration in self.weapon_declarations:
            if (declaration['weapon_profile'].parent_wargear == wargear and 
                declaration.get('weapon_instance', 1) == weapon_instance):
                return True
        return False
    
    def _has_split_fire(self, weapon_profile):
        """Check if a weapon has split fire ability"""
        return weapon_profile.is_split_fire()
    
    def _toggle_weapon_group_expansion(self, group_id):
        """Toggle the expansion state of a weapon group"""
        if group_id in self.expanded_weapon_groups:
            self.expanded_weapon_groups.remove(group_id)
        else:
            self.expanded_weapon_groups.add(group_id)
    
    def _is_weapon_group_expanded(self, group_id):
        """Check if a weapon group is expanded"""
        return group_id in self.expanded_weapon_groups
    
    def _handle_declaration_click(self, x, y):
        """Handle clicks on the declarations list"""
        # Calculate declarations list area
        declarations_x = 10
        declarations_y = 350 + self.scroll_offset
        declarations_width = self.width - 20
        declarations_height = 150
        
        if (declarations_x <= x <= declarations_x + declarations_width and 
            declarations_y <= y <= declarations_y + declarations_height):
            
            # Calculate which declaration was clicked
            click_y = y - declarations_y
            declaration_index = click_y // 35  # 35 pixels per declaration
            
            if 0 <= declaration_index < len(self.weapon_declarations):
                # Remove this declaration
                del self.weapon_declarations[declaration_index]
                return True
        
        return False
    
    def _handle_button_click(self, x, y):
        """Handle clicks on buttons"""
        # Execute button
        execute_x = 10
        execute_y = self.height - 50
        execute_width = 200
        execute_height = 35
        
        if (execute_x <= x <= execute_x + execute_width and 
            execute_y <= y <= execute_y + execute_height):
            self.execute_shooting()
            return True
        
        # Cancel button
        cancel_x = self.width - 160
        cancel_y = self.height - 50
        cancel_width = 140
        cancel_height = 35
        
        if (cancel_x <= x <= cancel_x + cancel_width and 
            cancel_y <= y <= cancel_y + cancel_height):
            print("✅ Cancel button clicked")
            self.hide()
            return True
        
        print(f"❌ Button click not detected at ({x}, {y})")
        print(f"   Dialog bounds: ({self.x}, {self.y}) to ({self.x + self.width}, {self.y + self.height})")
        print(f"   Execute button: ({execute_x}, {execute_y}) to ({execute_x + execute_width}, {execute_y + execute_height})")
        print(f"   Cancel button: ({cancel_x}, {cancel_y}) to ({cancel_x + cancel_width}, {cancel_y + cancel_height})")
        return False
    
    def get_max_scroll(self):
        """Calculate the maximum scroll offset based on content height"""
        # Calculate total content height
        weapons_height = len(self.available_weapons) * 50  # 50 pixels per weapon
        declarations_height = len(self.weapon_declarations) * 40  # 40 pixels per declaration
        total_content_height = weapons_height + declarations_height + 200  # Extra space for headers and padding

        # Calculate visible height (dialog height minus headers and buttons)
        visible_height = self.height - 100  # Account for title, buttons, and padding

        # Max scroll is the amount of content that doesn't fit
        return max(0, total_content_height - visible_height)

    def scroll(self, delta):
        """Scroll the dialog"""
        self.scroll_offset += delta * 20
        self.max_scroll = self.get_max_scroll()  # Update max scroll
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset))
    
    def update_hover(self, mouse_pos):
        """Update hover states"""
        x, y = mouse_pos
        
        # Update weapon hover
        self.hovered_weapon = -1
        weapons_x = self.x + 10
        weapons_y = self.y + 80  # Don't add scroll_offset here - it's for drawing only
        weapons_width = self.width - 20
        weapons_height = 200
        
        if (weapons_x <= x <= weapons_x + weapons_width and 
            weapons_y <= y <= weapons_y + weapons_height):
            # Account for scroll offset in the relative calculation
            relative_y = (y - weapons_y) - self.scroll_offset
            weapon_index = relative_y // 50
            if 0 <= weapon_index < len(self.available_weapons):
                self.hovered_weapon = weapon_index
    
    def execute_shooting(self):
        """Execute all shooting declarations"""
        if not self.weapon_declarations:
            print("❌ No shooting declarations to execute")
            return
        
        print(f"🎯 Executing {len(self.weapon_declarations)} shooting declarations...")
        
        # Execute shooting using the unit's new method
        success = self.unit.execute_shooting_declarations(self.weapon_declarations, self.game_map)
        
        if success:
            print(f"✅ {self.unit.name} completed shooting phase")
        else:
            print(f"❌ {self.unit.name} failed to execute shooting")
        
        # Call the callback with the results
        if self.callback:
            self.callback(self.weapon_declarations)
        
        # Hide the dialog
        self.hide()
    
    def draw(self, screen):
        """Draw the shooting declaration dialog"""
        if not self.visible:
            return
        
        # Create surface for dialog
        dialog_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Draw background
        pygame.draw.rect(dialog_surface, self.bg_color, (0, 0, self.width, self.height))
        pygame.draw.rect(dialog_surface, self.border_color, (0, 0, self.width, self.height), 2)
        
        # Draw title
        font_large = pygame.font.Font(None, 24)
        title_text = f"Shooting Declaration - {self.unit.name}"
        title_surface = font_large.render(title_text, True, self.text_color)
        dialog_surface.blit(title_surface, (10, 10))
        
        # Draw instructions
        font_small = pygame.font.Font(None, 16)
        instructions = "Select a weapon to target, or click Execute to resolve shooting"
        instructions_surface = font_small.render(instructions, True, self.text_color)
        dialog_surface.blit(instructions_surface, (10, 40))
        
        # Draw weapons list
        self._draw_weapons_list(dialog_surface, font_large, font_small)
        
        # Draw declarations list
        self._draw_declarations_list(dialog_surface, font_large, font_small)
        
        # Draw buttons
        self._draw_buttons(dialog_surface, font_large)
        
        # Draw dialog on screen
        screen.blit(dialog_surface, (self.x, self.y))
    
    def _draw_weapons_list(self, screen, font_large, font_small):
        """Draw the available weapons list"""
        x = 10  # Relative to dialog surface
        y = 80 + self.scroll_offset  # Relative to dialog surface
        
        # Draw section title
        title = "Available Weapons"
        title_surface = font_large.render(title, True, self.text_color)
        screen.blit(title_surface, (x, y - 20))
        
        # Get available weapons
        available_weapons = self._get_available_weapons()
        
        # Draw weapons
        for i, weapon_info in enumerate(available_weapons):
            weapon_y = y + i * 60  # Increased spacing for 3 lines
            
            weapon_profile = weapon_info['profile']
            is_group = weapon_info.get('is_group', False)
            
            # Check if this weapon/group is already declared
            if is_group:
                # For groups, check if any individual weapon is declared
                existing_declaration = any(
                    self._find_existing_declaration(w['profile'], w['weapon_instance']) 
                    for w in weapon_info['individual_weapons']
                )
            else:
                weapon_instance = weapon_info.get('weapon_instance', 1)
                existing_declaration = self._find_existing_declaration(weapon_profile, weapon_instance)
            
            has_split_fire = weapon_profile.is_split_fire()
            
            # Background color
            bg_color = self.button_color
            if i == self.hovered_weapon:
                bg_color = self.button_hover_color
            if (self.selected_weapon and 
                self.selected_weapon == weapon_profile):
                bg_color = self.selected_color
            
            # If weapon is already declared and can't split fire, gray it out
            if existing_declaration and not has_split_fire:
                bg_color = (60, 60, 60)  # Darker gray for unavailable weapons
            
            # Draw weapon background
            pygame.draw.rect(screen, bg_color, (x, weapon_y, self.width - 20, 50))
            pygame.draw.rect(screen, self.border_color, (x, weapon_y, self.width - 20, 50), 1)
            
            # Line 1: Weapon name with count/instance and keywords
            weapon_name = weapon_profile.parent_wargear.name
            if weapon_profile.name != 'default':
                weapon_name += f" - {weapon_profile.name}"
            
            if is_group:
                weapon_name += f" (x{weapon_info['count']})"  # Show count for groups
            else:
                weapon_instance = weapon_info.get('weapon_instance', 1)
                weapon_name += f" #{weapon_instance}"  # Show instance number for individuals
            
            # Render weapon name first
            weapon_surface = font_small.render(weapon_name, True, self.text_color)
            screen.blit(weapon_surface, (x + 5, weapon_y + 5))
            
            # Add keywords in blue color if they exist
            keywords = weapon_profile.get_keywords()
            if keywords:
                keywords_text = f" | {', '.join(keywords)}"
                keywords_surface = font_small.render(keywords_text, True, (100, 149, 237))  # Blue accent color
                # Position keywords after the weapon name
                keywords_x = x + 5 + weapon_surface.get_width()
                screen.blit(keywords_surface, (keywords_x, weapon_y + 5))
            
            # Draw expand/collapse button for groups
            if is_group:
                button_x = self.width - 35
                button_y = weapon_y + 5
                button_size = 20
                
                # Draw button background
                pygame.draw.rect(screen, (80, 80, 80), (button_x, button_y, button_size, button_size))
                pygame.draw.rect(screen, (100, 100, 100), (button_x, button_y, button_size, button_size), 1)
                
                # Draw + or - symbol
                symbol = "-" if self._is_weapon_group_expanded(weapon_info['group_id']) else "+"
                symbol_surface = font_small.render(symbol, True, self.text_color)
                symbol_rect = symbol_surface.get_rect(center=(button_x + button_size//2, button_y + button_size//2))
                screen.blit(symbol_surface, symbol_rect)
            
            # Line 2: Full weapon stats
            stats_parts = []
            
            # Range
            if hasattr(weapon_profile, 'range'):
                if weapon_profile.range.max == 0:
                    stats_parts.append("Melee")
                else:
                    stats_parts.append(f"Range: {weapon_profile.range.max}\"")
            
            # Attacks
            if hasattr(weapon_profile, 'attacks'):
                if hasattr(weapon_profile.attacks, 'value'):
                    stats_parts.append(f"A: {weapon_profile.attacks.value}")
                else:
                    stats_parts.append(f"A: {weapon_profile.attacks}")
            
            # Skill (BS for ranged, WS for melee)
            if hasattr(weapon_profile, 'skill'):
                if weapon_profile.range.max == 0:
                    stats_parts.append(f"WS: {weapon_profile.skill}+")
                else:
                    stats_parts.append(f"BS: {weapon_profile.skill}+")
            
            # Strength
            if hasattr(weapon_profile, 'strength'):
                stats_parts.append(f"S: {weapon_profile.strength}")
            
            # AP
            if hasattr(weapon_profile, 'ap'):
                ap_val = weapon_profile.ap
                if ap_val == 0:
                    stats_parts.append("AP: -")
                else:
                    stats_parts.append(f"AP: {ap_val}")
            
            # Damage
            if hasattr(weapon_profile, 'damage'):
                if hasattr(weapon_profile.damage, 'value'):
                    stats_parts.append(f"D: {weapon_profile.damage.value}")
                else:
                    stats_parts.append(f"D: {weapon_profile.damage}")
            
            # Add split fire indicator
            if has_split_fire:
                stats_parts.append("Split Fire")
            
            # Add group indicator for collapsed groups
            if is_group:
                stats_parts.append("Click to target all")
            
            stats = " | ".join(stats_parts)
            stats_surface = font_small.render(stats, True, self.text_color)
            screen.blit(stats_surface, (x + 5, weapon_y + 20))
    
    def _draw_declarations_list(self, screen, font_large, font_small):
        """Draw the shooting declarations list"""
        x = 10  # Relative to dialog surface
        y = 350 + self.scroll_offset  # Relative to dialog surface
        
        # Draw section title
        title = "Declarations Made"
        title_surface = font_large.render(title, True, self.text_color)
        screen.blit(title_surface, (x, y - 20))
        
        # Draw declarations
        for i, declaration in enumerate(self.weapon_declarations):
            declaration_y = y + i * 35  # Larger spacing
            
            # Background
            pygame.draw.rect(screen, self.selected_color, (x, declaration_y, self.width - 20, 30))
            pygame.draw.rect(screen, self.border_color, (x, declaration_y, self.width - 20, 30), 1)
            
            # Declaration text (shortened)
            weapon_name = declaration['weapon_profile'].parent_wargear.name
            if declaration['weapon_profile'].name != 'default':
                weapon_name += f" - {declaration['weapon_profile'].name}"
            weapon_instance = declaration.get('weapon_instance', 1)
            weapon_name += f" #{weapon_instance}"
            target_name = declaration['target_unit'].name[:15] + "..." if len(declaration['target_unit'].name) > 15 else declaration['target_unit'].name
            declaration_text = f"{weapon_name} -> {target_name}"
            text_surface = font_small.render(declaration_text, True, self.text_color)
            screen.blit(text_surface, (x + 5, declaration_y + 5))
    
    def _draw_buttons(self, screen, font_large):
        """Draw the dialog buttons"""
        # Execute button (relative to dialog surface, not screen)
        execute_x = 10
        execute_y = self.height - 50
        execute_width = 200
        execute_height = 35
        
        pygame.draw.rect(screen, self.button_color, (execute_x, execute_y, execute_width, execute_height))
        pygame.draw.rect(screen, self.border_color, (execute_x, execute_y, execute_width, execute_height), 2)
        
        execute_text = "Execute Shooting"
        execute_surface = font_large.render(execute_text, True, self.text_color)
        text_rect = execute_surface.get_rect(center=(execute_x + execute_width//2, execute_y + execute_height//2))
        screen.blit(execute_surface, text_rect)
        
        # Cancel button (relative to dialog surface, not screen)
        cancel_x = self.width - 160
        cancel_y = self.height - 50
        cancel_width = 140
        cancel_height = 35
    
        pygame.draw.rect(screen, self.button_color, (cancel_x, cancel_y, cancel_width, cancel_height))
        pygame.draw.rect(screen, self.border_color, (cancel_x, cancel_y, cancel_width, cancel_height), 2)
        
        cancel_text = "Cancel"
        cancel_surface = font_large.render(cancel_text, True, self.text_color)
        text_rect = cancel_surface.get_rect(center=(cancel_x + cancel_width//2, cancel_y + cancel_height//2))
        screen.blit(cancel_surface, text_rect)

    def select_weapon_for_targeting(self, weapon_profile, weapon_instance=1):
        """Select a weapon and enter targeting mode"""
        print(f"🎯 select_weapon_for_targeting called with {weapon_profile.parent_wargear.name} #{weapon_instance}")
        self.selected_weapon = weapon_profile
        self.selected_weapon_instance = weapon_instance
        self.selected_weapon_group = None
        self.is_targeting_mode = True
        self.visible = False  # Close dialog

        # Set weapon profile on game view for range visualization
        if hasattr(self, 'game_view') and self.game_view:
            self.game_view.selected_weapon_profile = weapon_profile

        print(f"🎯 Targeting mode set: is_targeting_mode={self.is_targeting_mode}, selected_weapon={self.selected_weapon}")
        print(f"🎯 Selected {weapon_profile.parent_wargear.name} #{weapon_instance} for targeting - click on battlefield")
    
    def select_weapon_group_for_targeting(self, weapon_group_info):
        """Select a weapon group and enter targeting mode"""
        print(f"🎯 select_weapon_group_for_targeting called with {weapon_group_info['profile'].parent_wargear.name} (x{weapon_group_info['count']})")
        self.selected_weapon = weapon_group_info['profile']
        self.selected_weapon_group = weapon_group_info
        self.selected_weapon_instance = None
        self.is_targeting_mode = True
        self.visible = False  # Close dialog

        # Set weapon profile on game view for range visualization
        if hasattr(self, 'game_view') and self.game_view:
            self.game_view.selected_weapon_profile = weapon_group_info['profile']

        print(f"🎯 Targeting mode set: is_targeting_mode={self.is_targeting_mode}, selected_weapon_group={self.selected_weapon_group}")
        print(f"🎯 Selected weapon group {weapon_group_info['profile'].parent_wargear.name} (x{weapon_group_info['count']}) for targeting - click on battlefield")
    
    def handle_battlefield_targeting(self, x: float, y: float) -> bool:
        """Handle clicking on the battlefield for targeting."""
        if not self.selected_weapon:
            print("❌ No weapon selected for targeting")
            return False
            
        # Get clicked unit using game view's unit detection
        clicked_unit = None
        if self.game_view:
            clicked_unit = self.game_view.get_unit_at_position(x, y, needs_conversion=False)
        
        if not clicked_unit:
            print("❌ No unit found at clicked position")
            return False

        # Check if this is a valid target
        if not self._can_target_unit(self.selected_weapon, clicked_unit):
            print(f"❌ {clicked_unit.name} is not a valid target for {self.selected_weapon.name}")
            return False

        # Handle weapon group targeting
        if self.selected_weapon_group:
            # Create individual declarations for each weapon instance in the group
            for weapon_info in self.selected_weapon_group['individual_weapons']:
                self.weapon_declarations.append({
                    'weapon_profile': self.selected_weapon,
                    'target_unit': clicked_unit,
                    'models': [weapon_info['model']],  # Single model per declaration
                    'weapon_instance': weapon_info['weapon_instance']
                })
            print(f"✅ {self.unit.name} targeting {clicked_unit.name} with {self.selected_weapon.parent_wargear.name} group (x{self.selected_weapon_group['count']})")
        else:
            # Handle individual weapon targeting
            self.weapon_declarations.append({
                'weapon_profile': self.selected_weapon,
                'target_unit': clicked_unit,
                'models': self._get_models_with_weapon(self.selected_weapon),
                'weapon_instance': getattr(self, 'selected_weapon_instance', 1)
            })
            print(f"✅ {self.unit.name} targeting {clicked_unit.name} with {self.selected_weapon.parent_wargear.name} #{getattr(self, 'selected_weapon_instance', 1)}")
        
        # Clear targeting mode and return success
        self.clear_targeting_mode()
        return True
    
    def clear_targeting_mode(self):
        """Clear targeting mode (ESC key)"""
        if self.is_targeting_mode:
            self.is_targeting_mode = False
            self.selected_weapon = None
            self.selected_weapon_instance = None
            self.selected_weapon_group = None
            self.visible = True  # Reopen dialog

            # Clear weapon profile on game view to remove range visualization
            if hasattr(self, 'game_view') and self.game_view:
                self.game_view.selected_weapon_profile = None

            print("❌ Targeting mode cleared")