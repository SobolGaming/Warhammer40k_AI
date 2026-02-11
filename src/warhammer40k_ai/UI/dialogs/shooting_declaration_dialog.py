import pygame
import math
from typing import List
import types
from .base_dialog import BaseDialog
import logging
logger = logging.getLogger(__name__)

# Enhanced Colors
PANEL_BG = (50, 50, 50)
PANEL_BORDER = (100, 100, 100)
BUTTON_BG = (70, 70, 70)
BUTTON_HOVER = (100, 100, 100)
BUTTON_SELECTED = (120, 120, 120)
TEXT_PRIMARY = (255, 255, 255)
TEXT_SECONDARY = (200, 200, 200)
TEXT_ACCENT = (100, 149, 237)  # Blue accent color for keywords


class ShootingDeclarationDialog(BaseDialog):
    """
    Advanced shooting declaration dialog that allows players to declare multiple weapons
    and targets before executing all shooting simultaneously.
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        # Initialize BaseDialog with draggable functionality
        super().__init__(screen_width, screen_height, width=625, height=600, draggable=True)
        
        # Unit and callback
        self.unit = None
        self.callback = None
        self.game_map = None
        self.game_view = None
        
        # Weapon selection and targeting state
        self.selected_weapon = None  # The currently selected weapon profile
        self.is_targeting_mode = False
        self._linked_fire_origin_unit_id = None
        self._infernal_puppeteer_origin_unit_id = None
        self._infernal_puppeteer_origin_chosen = False
        
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
        # Targeting cache removed for performance; validation now happens on click only
        self.out_of_phase = False
        self.allow_actions = True
        self.last_execution_success = None
        self.decision_request = None
    
    def show(self, unit, callback, game_map=None, game_view=None, *, out_of_phase: bool = False, allow_actions: bool | None = None, decision_request=None):
        """Show the shooting declaration dialog."""
        # Call parent show method
        super().show(callback)

        self.unit = unit
        self.game_map = game_map
        self.game_view = game_view
        self.out_of_phase = bool(out_of_phase)
        self.decision_request = decision_request
        if allow_actions is None:
            self.allow_actions = not self.out_of_phase
        else:
            self.allow_actions = bool(allow_actions)
        
        # Clear previous state
        self.weapon_declarations = []
        self.selected_weapon = None
        self.is_targeting_mode = False
        self._linked_fire_origin_unit_id = None
        self._infernal_puppeteer_origin_unit_id = None
        self._infernal_puppeteer_origin_chosen = False
        # No precomputed validation cache
        
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

        # Create buttons using BaseDialog button system
        self._create_dialog_buttons()

        logger.info(f"INFO: ShootingDeclarationDialog shown for {unit.name}")
        logger.info(f"INFO: Found {len(self.available_weapons)} available weapons")
        logger.info(f"INFO: Found {len(self.available_targets)} available targets")

        # Infernal Puppeteer: optional origin selection when selected to shoot.
        self._maybe_prompt_infernal_puppeteer_origin()

    def _create_dialog_buttons(self):
        """Create the Execute and Cancel buttons using BaseDialog button system"""
        # Add Execute button
        self.add_button('execute', 10, self.height - 50, 200, 35)

        # Add Cancel button
        self.add_button('cancel', self.width - 160, self.height - 50, 140, 35)

        if self.allow_actions:
            # Check if unit has Deathstrike capability
            has_deathstrike = False
            if self.unit:
                army = self.unit.get_parent_army()
                deathstrike_mgr = getattr(army, "deathstrike", None)
                if deathstrike_mgr is not None and bool(getattr(self.unit, "has_plasma_warhead_weapon", lambda: False)()):
                    has_deathstrike = True

            # Add Deathstrike button if available
            if has_deathstrike:
                self.add_button('start_deathstrike', 10, self.height - 185, 200, 35)

            # Add additional Mission Action buttons (The Ritual / Move Hazard)
            self.add_button('start_the_ritual', 10, self.height - 140, 200, 35)
            self.add_button('start_move_hazard', 220, self.height - 140, 200, 35)

            # Add Mission Action buttons (Terraform / Sabotage / Burn Objective)
            # Place above the bottom row
            self.add_button('start_terraform', 10, self.height - 95, 200, 35)
            self.add_button('start_sabotage', 220, self.height - 95, 200, 35)
            self.add_button('start_burn_objective', 430, self.height - 95, 185, 35)

    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button click events from BaseDialog"""
        if button_name == 'execute':
            self.execute_shooting()
            return True
        elif button_name == 'cancel':
            logger.info("INFO: Cancel button clicked")
            self._resolve_skip()
            return True
        if not self.allow_actions and button_name.startswith("start_"):
            return False
        elif button_name == 'start_deathstrike':
            return self._try_start_deathstrike()
        elif button_name == 'start_terraform':
            return self._try_start_terraform()
        elif button_name == 'start_sabotage':
            return self._try_start_sabotage()
        elif button_name == 'start_burn_objective':
            return self._try_start_burn_objective()
        elif button_name == 'start_the_ritual':
            return self._try_start_the_ritual()
        elif button_name == 'start_move_hazard':
            return self._try_start_move_hazard()
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        """Handle clicks within dialog area"""
        x, y = mouse_pos

        # Convert to dialog-relative coordinates, accounting for title bar
        relative_x = x - self.x
        content_y = self.title_bar_height if self.draggable else 0
        relative_y = y - self.y - content_y

        # Handle weapon selection clicks
        if self._handle_weapon_click(relative_x, relative_y):
            return True

        # Handle declaration list clicks (to remove declarations)
        if self._handle_declaration_click(relative_x, relative_y):
            return True

        return False
    
    def hide(self):
        """Hide the shooting declaration dialog."""
        # If the unit injected temporary Firing Deck virtual weapons, clear them on close (execute or cancel).
        try:
            if self.unit is not None and hasattr(self.unit, "clear_firing_deck_virtual_wargear"):
                self.unit.clear_firing_deck_virtual_wargear()
        except Exception:
            pass

        self.visible = False
        self.unit = None
        self.callback = None
        self.game_map = None
        self.out_of_phase = False
        self.allow_actions = True
        self.last_execution_success = None
        self.decision_request = None
        try:
            self.force_single_target_unit = None
        except Exception:
            pass

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
                    if wargear.is_bubblechukka():
                        profile = None
                        for candidate in wargear.profiles.values():
                            if getattr(candidate, "is_bubblechukka", lambda: False)():
                                profile = candidate
                                break
                        if profile is None:
                            profile = next(iter(wargear.profiles.values()), None)
                        if profile is None:
                            continue
                        # Check if weapon can be used
                        if self._can_use_weapon(profile):
                            # ONE SHOT: if this model already used this weapon, don't list it as available.
                            if profile.is_one_shot():
                                key = profile.one_shot_key()
                                used = getattr(model, "_one_shot_used", set())
                                if key and key in used:
                                    continue
                            individual_weapons.append({
                                'profile': profile,
                                'wargear': wargear,
                                'profile_name': "random profile",
                                'model': model,
                                'weapon_instance': len([w for w in individual_weapons if w['profile'] == profile]) + 1
                            })
                        continue
                    for profile_name, profile in wargear.profiles.items():
                        # Check if weapon can be used
                        if self._can_use_weapon(profile):
                            # ONE SHOT: if this model already used this weapon, don't list it as available.
                            if profile.is_one_shot():
                                key = profile.one_shot_key()
                                used = getattr(model, "_one_shot_used", set())
                                if key and key in used:
                                    continue
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
            profile_id = weapon['profile'].id
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

        # Formless Horror: remove targets this unit is blocked from targeting this phase.
        try:
            game = None
            if self.game_view is not None:
                game = getattr(self.game_view, "game", None)
            if game is None and self.unit is not None:
                try:
                    game = self.unit.get_parent_army().player.game
                except Exception:
                    game = None
            filtered = []
            for target in list(enemy_units or []):
                if hasattr(self.unit, "_formless_horror_target_blocked"):
                    if self.unit._formless_horror_target_blocked(target, game=game):
                        continue
                filtered.append(target)
            enemy_units = filtered
        except Exception:
            pass

        return enemy_units
    
    def _can_use_weapon(self, weapon_profile):
        """Check if a weapon can be used."""
        # If the unit is performing an Action, it cannot shoot
        try:
            if getattr(self.unit.round_state, 'action_locked_until_turn_end', False):
                return False
        except Exception:
            pass
        # Check if the unit has already shot
        if (not self.out_of_phase) and self.unit.round_state.shot_this_round:
            return False
        
        # Check for restrictions due to Advance or Fall Back
        if self.unit.round_state.advanced_this_round and not self.unit.can_shoot_after_advance(weapon_profile):
            return False
        if self.unit.round_state.fell_back_this_round and not self.unit.can_shoot_after_fall_back(weapon_profile):
            return False
        if hasattr(weapon_profile, "is_plasma_warhead") and weapon_profile.is_plasma_warhead():
            models = list(getattr(self.unit, "get_plasma_warhead_models", lambda: [])() or [])
            if not models:
                return False
            can_shoot_fn = getattr(weapon_profile, "can_shoot_plasma_warhead", None)
            if callable(can_shoot_fn):
                can_shoot, _reason = can_shoot_fn(models[0], out_of_phase=self.out_of_phase)
                if not can_shoot:
                    return False
        if not self._can_add_ctan_power_weapon(weapon_profile):
            return False
        return True

    def _is_ctan_power_profile(self, weapon_profile) -> bool:
        checker = getattr(self.unit, "_is_ctan_power_profile", None)
        if callable(checker):
            return bool(checker(weapon_profile))
        return False

    def _ctan_power_selection_limit(self) -> int:
        getter = getattr(self.unit, "get_ctan_power_selection_limit", None)
        if callable(getter):
            return int(getter() or 0)
        return 0

    def _ctan_power_declaration_keys(self) -> set[str]:
        keys = set()
        key_getter = getattr(self.unit, "_ctan_power_profile_key", None)
        if not callable(key_getter):
            return keys
        for decl in list(self.weapon_declarations or []):
            profile = decl.get("weapon_profile")
            if not self._is_ctan_power_profile(profile):
                continue
            keys.add(str(key_getter(profile)))
        return keys

    def _can_add_ctan_power_weapon(self, weapon_profile) -> bool:
        if not self._is_ctan_power_profile(weapon_profile):
            return True
        limit = self._ctan_power_selection_limit()
        if limit <= 0:
            return True
        key_getter = getattr(self.unit, "_ctan_power_profile_key", None)
        if not callable(key_getter):
            return True
        key = str(key_getter(weapon_profile))
        selected = self._ctan_power_declaration_keys()
        if key in selected:
            return True
        return len(selected) < limit

    def _show_ctan_limit_error(self) -> None:
        limit = self._ctan_power_selection_limit()
        message = f"Powers of the C'tan: select up to {int(limit)} different C'tan Powers weapons."
        logger.error(f"ERROR: {message}")
        try:
            if self.game_view is not None:
                self.game_view._mission_popup = {
                    "title": "Powers of the C'tan",
                    "body": message,
                }
        except Exception:
            pass

    def _try_start_deathstrike(self) -> bool:
        """Open Deathstrike Missile action dialog (Designate/Adjust/None)."""
        if not self.game_view or not hasattr(self.game_view, 'game'):
            return False
        game = self.game_view.game

        # Check if unit has Deathstrike capability
        army = self.unit.get_parent_army()
        deathstrike_mgr = getattr(army, "deathstrike", None)
        if deathstrike_mgr is None or not bool(getattr(self.unit, "has_plasma_warhead_weapon", lambda: False)()):
            logger.error("ERROR: Deathstrike: No Deathstrike manager found")
            return False

        # Import the Deathstrike dialog
        from .deathstrike_action_dialog import DeathstrikeActionDialog

        if not hasattr(self.game_view, "deathstrike_action_dialog") or self.game_view.deathstrike_action_dialog is None:
            self.game_view.deathstrike_action_dialog = DeathstrikeActionDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height()
            )

        dialog = self.game_view.deathstrike_action_dialog

        def _on_complete():
            """Called when Deathstrike action is complete."""
            logger.info("✅ Deathstrike action complete")
            # Don't hide shooting dialog - user can continue with shooting

        dialog.show(
            unit=self.unit,
            game_view=self.game_view,
            on_complete=_on_complete
        )

        try:
            self.game_view.dialog_manager.open(dialog, modal=True)
        except Exception:
            pass

        return True

    def _try_start_terraform(self) -> bool:
        if not self.game_view or not hasattr(self.game_view, 'game'):
            return False
        game = self.game_view.game
        check = game.can_start_terraform(self.unit)
        if not check.get('valid'):
            logger.error(f"ERROR: Cannot start Terraform: {check.get('reason')}")
            return False
        result = game.start_terraform_action(self.unit)
        logger.info("INFO: Terraform Action started")
        # Lock dialog to prevent shooting; optionally close dialog
        self.hide()
        return True

    def _try_start_sabotage(self) -> bool:
        if not self.game_view or not hasattr(self.game_view, 'game'):
            return False
        game = self.game_view.game
        check = game.can_start_sabotage(self.unit)
        if not check.get('valid'):
            logger.error(f"ERROR: Cannot start Sabotage: {check.get('reason')}")
            return False
        result = game.start_sabotage_action(self.unit)
        logger.info("INFO: Sabotage Action started")
        self.hide()
        return True

    def _try_start_burn_objective(self) -> bool:
        if not self.game_view or not hasattr(self.game_view, 'game'):
            return False
        game = self.game_view.game
        # Reuse terraform-like check but specific API if available
        if not hasattr(game, 'can_start_burn_objective'):
            logger.error("ERROR: Burn Objective not available for current primary")
            return False
        check = game.can_start_burn_objective(self.unit)
        if not check.get('valid'):
            logger.error(f"ERROR: Cannot start Burn Objective: {check.get('reason')}")
            return False
        result = game.start_burn_objective_action(self.unit)
        logger.info("INFO: Burn Objective Action started")
        self.hide()
        return True

    def _try_start_the_ritual(self) -> bool:
        if not self.game_view or not hasattr(self.game_view, 'game'):
            return False
        game = self.game_view.game
        if not hasattr(game, "can_start_the_ritual") or not hasattr(game, "start_the_ritual_action"):
            logger.error("ERROR: The Ritual action is not available")
            return False

        # Open point picker modal: user clicks battlefield to choose placement.
        from .battlefield_point_pick_dialog import BattlefieldPointPickDialog

        if not hasattr(self.game_view, "battlefield_point_pick_dialog") or self.game_view.battlefield_point_pick_dialog is None:
            self.game_view.battlefield_point_pick_dialog = BattlefieldPointPickDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())

        picker = self.game_view.battlefield_point_pick_dialog

        def _validate(x: float, y: float) -> dict:
            return game.can_start_the_ritual(self.unit, new_objective_xy=(x, y))

        def _confirm(pt):
            x, y = pt
            res = game.start_the_ritual_action(self.unit, new_objective_xy=(x, y))
            if not res.get("valid", False):
                logger.error(f"ERROR: Cannot start The Ritual: {res.get('reason')}")
                return
            logger.info("INFO: The Ritual Action started")
            self.hide()

        picker.show(
            game_view=self.game_view,
            title="The Ritual",
            instructions="Click a point in No Man's Land to place the new objective marker.",
            validate_cb=_validate,
            on_confirm=_confirm,
            on_cancel=lambda: None,
        )
        try:
            self.game_view.dialog_manager.open(picker, modal=True)
        except Exception:
            pass
        return True

    def _try_start_move_hazard(self) -> bool:
        if not self.game_view or not hasattr(self.game_view, 'game'):
            return False
        game = self.game_view.game
        if not hasattr(game, "can_start_move_hazard") or not hasattr(game, "start_move_hazard_action"):
            logger.error("ERROR: Move Hazard action is not available")
            return False

        # Build eligible hazard objectives: controlled by player, marked hazard, and this unit is within range.
        actor = self.unit.get_parent_army().player
        eligible = []
        for obj in getattr(game.map, "objectives", []) or []:
            loc = getattr(obj, "location", None)
            if not loc or getattr(loc, "removed", False):
                continue
            if not bool(getattr(loc, "is_hazard", False)):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(game)
            if getattr(loc, "controlling_player", None) is not actor:
                continue
            try:
                if game._unit_within_range_of_objective(self.unit) is not obj:
                    continue
            except Exception:
                continue
            eligible.append(obj)

        if not eligible:
            logger.error("ERROR: No eligible Hazard objective markers in range that you control")
            return False

        from .hazard_objective_select_dialog import HazardObjectiveSelectDialog
        from .battlefield_point_pick_dialog import BattlefieldPointPickDialog

        if not hasattr(self.game_view, "hazard_objective_select_dialog") or self.game_view.hazard_objective_select_dialog is None:
            self.game_view.hazard_objective_select_dialog = HazardObjectiveSelectDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
        if not hasattr(self.game_view, "battlefield_point_pick_dialog") or self.game_view.battlefield_point_pick_dialog is None:
            self.game_view.battlefield_point_pick_dialog = BattlefieldPointPickDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())

        selector = self.game_view.hazard_objective_select_dialog
        picker = self.game_view.battlefield_point_pick_dialog

        def _after_select(hazard_obj):
            def _validate(x: float, y: float) -> dict:
                return game.can_start_move_hazard(self.unit, hazard_objective=hazard_obj, new_xy=(x, y))

            def _confirm(pt):
                x, y = pt
                res = game.start_move_hazard_action(self.unit, hazard_objective=hazard_obj, new_xy=(x, y))
                if not res.get("valid", False):
                    logger.error(f"ERROR: Cannot start Move Hazard: {res.get('reason')}")
                    return
                logger.info("INFO: Move Hazard Action started")
                self.hide()

            picker.show(
                game_view=self.game_view,
                title="Move Hazard",
                instructions="Click a destination for the Hazard objective marker (up to 6\").",
                validate_cb=_validate,
                on_confirm=_confirm,
                on_cancel=lambda: None,
            )
            try:
                self.game_view.dialog_manager.open(picker, modal=True)
            except Exception:
                pass

        selector.show(game_view=self.game_view, choices=eligible, on_confirm=_after_select, on_cancel=lambda: None)
        try:
            self.game_view.dialog_manager.open(selector, modal=True)
        except Exception:
            pass
        return True
    
    def _can_target_unit(self, weapon_profile, target_unit):
        """Fast check if a weapon can target a specific unit (uses range prefilter and short-circuit)."""
        valid, _ = self._validate_target_with_reason(weapon_profile, target_unit)
        return valid

    def _get_weapon_display_name(self, weapon_profile) -> str:
        name = weapon_profile.parent_wargear.name
        if getattr(weapon_profile, "is_bubblechukka", lambda: False)():
            return f"{name} (random profile)"
        try:
            profile_name = getattr(weapon_profile, 'name', 'default')
            if profile_name and profile_name != 'default':
                name = f"{name} - {profile_name}"
        except Exception:
            pass
        return name

    def _validate_target_with_reason(self, weapon_profile, target_unit):
        """Validate target with specific reason. Optimized:
        - Prefilter by range using edge-to-edge distances
        - Short-circuit per unit: as soon as any shooter model is eligible, accept
        Returns (is_valid: bool, reason: str)
        """
        # Determine max range
        weapon_range_max = 0
        if hasattr(weapon_profile, 'range') and hasattr(weapon_profile.range, 'max'):
            weapon_range_max = weapon_profile.range.max or 0

        # Only consider models that actually have this weapon
        shooter_models = self._get_models_with_weapon(weapon_profile)
        if not shooter_models:
            return (False, "No models with this weapon")

        # Quick global range prefilter: find closest base distance
        closest_distance = float('inf')
        any_in_range = False
        for shooting_model in shooter_models:
            if not shooting_model.is_alive:
                continue
            for target_model in target_unit.models:
                if not target_model.is_alive:
                    continue
                from ...utility.aura_utils import distance_between_models_bases_3d
                distance = float(distance_between_models_bases_3d(shooting_model, target_model))
                if distance <= weapon_range_max:
                    any_in_range = True
                    # As soon as we detect in-range for this shooter, we can attempt LoS via unit validator
                    break
                if distance < closest_distance:
                    closest_distance = distance
            if any_in_range:
                # Only now call the heavy validator (includes LoS) once per in-range shooter
                if hasattr(self.unit, '_can_model_shoot_weapon_at_target') and self.game_map is not None:
                    if self.unit._can_model_shoot_weapon_at_target(shooting_model, weapon_profile, target_unit, self.game_map):
                        return (True, "")
                else:
                    # If no validator available, treat in-range as valid
                    return (True, "")
                # Reset for next shooter: they may have different LoS
                any_in_range = False

        if closest_distance == float('inf'):
            return (False, "No valid target models found")

        if not any_in_range:
            return (False, f"Out of range: closest is {closest_distance:.1f}\" > {weapon_range_max}\"")

        # Reaching here means at least one shooter was in range but failed LoS/other constraints
        return (False, "No line of sight from any model or shooting restricted")

    def _validate_click_target_with_reason(self, weapon_profile, target_unit, clicked_model):
        """Validate target using specific clicked target model when available.
        Uses true minimum edge-to-edge distance across all shooter/target model pairs.
        """
        # Phase eligibility checks (so the player gets a clear reason on click)
        try:
            if hasattr(self.unit, "round_state") and getattr(self.unit.round_state, "advanced_this_round", False):
                if hasattr(self.unit, "can_shoot_after_advance") and (not self.unit.can_shoot_after_advance(weapon_profile)):
                    return (False, "Unit advanced and cannot shoot with this weapon")
            if hasattr(self.unit, "round_state") and getattr(self.unit.round_state, "fell_back_this_round", False):
                if hasattr(self.unit, "can_shoot_after_fall_back") and (not self.unit.can_shoot_after_fall_back(weapon_profile)):
                    return (False, "Unit fell back and cannot shoot with this weapon")
        except Exception:
            pass

        # Shooter models that have this weapon
        shooter_models = self._get_models_with_weapon(weapon_profile)
        if not shooter_models:
            return (False, "No models with this weapon")

        # Range check first
        weapon_range_max = 0
        if hasattr(weapon_profile, 'range') and hasattr(weapon_profile.range, 'max'):
            weapon_range_max = weapon_profile.range.max or 0

        in_range_any = False
        closest_edge = float('inf')
        best_pair = (None, None)
        # If a clicked target model was found and alive, prefer distances to it; otherwise consider all target models
        target_models_iter = [clicked_model] if (clicked_model and clicked_model.is_alive and clicked_model in target_unit.models) else [tm for tm in target_unit.models if tm.is_alive]
        for sm in shooter_models:
            if not sm.is_alive:
                continue
            for tm in target_models_iter:
                from ...utility.aura_utils import distance_between_models_bases_3d
                edge = float(distance_between_models_bases_3d(sm, tm))
                if edge <= weapon_range_max:
                    in_range_any = True
                    shooting_model = sm
                    target_model = tm
                    break
                if edge < closest_edge:
                    closest_edge = edge
                    best_pair = (sm, tm)
            if in_range_any:
                break
        if not in_range_any:
            # Avoid misleading rounding when barely out of range
            display_edge = math.ceil(closest_edge * 10.0) / 10.0
            return (False, f"Out of range: {display_edge:.1f}\" > {weapon_range_max}\"")

        # Use the unit's validator to get true legality (includes LoS and special rules)
        if hasattr(self.unit, '_can_model_shoot_weapon_at_target') and self.game_map is not None:
            # If validator returns False, try to infer common reasons
            if not self.unit._can_model_shoot_weapon_at_target(shooting_model, weapon_profile, target_unit, self.game_map):
                # Ranged targeting restriction (e.g., Lone Operative or other range caps).
                try:
                    limit, sources = target_unit.get_ranged_targeting_restriction(game_map=self.game_map)
                except Exception:
                    limit, sources = (None, [])
                if limit is not None:
                    tm_ref = target_model if 'target_model' in locals() and target_model is not None else best_pair[1]
                    from ...utility.aura_utils import distance_between_models_bases_3d
                    dist_limit = float(distance_between_models_bases_3d(shooting_model, tm_ref))
                    if dist_limit > float(limit):
                        label = str((sources or ["Ranged targeting restriction"])[0] or "Ranged targeting restriction")
                        return (False, f"{label} beyond {int(limit)}\"")
                # Engagement restrictions
                if not self.unit._can_shoot_while_engaged(shooting_model, weapon_profile, target_unit, self.game_map):
                    return (False, "Engaged: weapon cannot fire or target invalid")
                # Otherwise attribute to LoS
                return (False, "No line of sight")
        # If no validator, treat as valid if in range
        return (True, "")
    
    def _has_line_of_sight(self, shooting_model, target_model):
        """Check if shooting model has line of sight to target model."""
        # Simplified line of sight check
        return True
    
    def _get_models_with_weapon(self, weapon_profile):
        """Get all models in the unit that have this weapon."""
        models = []
        for model in self.unit.models:
            if model.is_alive:
                # ONE SHOT: exclude models that already used this weapon.
                if weapon_profile.is_one_shot():
                    key = weapon_profile.one_shot_key()
                    used = getattr(model, "_one_shot_used", set())
                    if key and key in used:
                        continue
                for wargear in model.wargear:
                    for profile_name, profile in wargear.profiles.items():
                        if profile == weapon_profile:
                            models.append(model)
                            break
        return models

    def _get_model_for_weapon_instance(self, weapon_profile, weapon_instance):
        """Get the specific model assigned to a weapon instance.

        For individual weapon instances (e.g., "Ectoplasma cannon #2"), this ensures
        each declaration uses only one model, preventing multiple attacks per declaration.

        Args:
            weapon_profile: The weapon profile to find models for
            weapon_instance: The weapon instance number (1-based)

        Returns:
            List containing a single model, or empty list if no models available
        """
        models_with_weapon = self._get_models_with_weapon(weapon_profile)
        if models_with_weapon:
            # Use modulo to cycle through available models for multiple weapon instances
            model_index = (weapon_instance - 1) % len(models_with_weapon)
            return [models_with_weapon[model_index]]
        return []
    
    def handle_event(self, event):
        """Handle pygame events"""

        # If not visible and not in targeting mode, ignore all events
        if not self.visible and not self.is_targeting_mode:
            return False

        # If in targeting mode, only handle ESC key and let all other events pass through
        if self.is_targeting_mode:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                logger.info("INFO: ESC pressed in targeting mode - clearing targeting")
                self.clear_targeting_mode()
                return True
            return False  # Let other handlers (like battle phase) handle targeting clicks

        # Handle mouse wheel scrolling
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):  # Mouse wheel
            if event.button == 4:  # Scroll up
                self.scroll_offset = max(0, self.scroll_offset - 50)
            else:  # Scroll down
                self.scroll_offset = min(self.get_max_scroll(), self.scroll_offset + 50)
            return True

        # Handle mouse motion for hover updates
        if event.type == pygame.MOUSEMOTION:
            self.update_hover(event.pos)
            return True  # Consume mouse motion events

        # Let BaseDialog handle other events (dragging, button clicks, etc.)
        result = super().handle_event(event)
        
        # Ensure all events are consumed when dialog is visible
        if self.visible:
            return True
        
        return result

    def should_passthrough_event(self, event) -> bool:
        """
        While in battlefield targeting mode, we want battlefield clicks to be handled by the
        phase handler (which converts screen->game coords and calls handle_battlefield_targeting()).
        Without this, DialogManager will consume clicks because is_targeting_mode marks us "active".
        """
        if not bool(getattr(self, "is_targeting_mode", False)):
            return False
        try:
            etype = getattr(event, "type", None)
            if etype in (pygame.KEYDOWN, pygame.KEYUP):
                return getattr(event, "key", None) != pygame.K_ESCAPE
            return etype in (
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEBUTTONUP,
                pygame.MOUSEWHEEL,
            )
        except Exception:
            return False
    

    
    def _handle_weapon_click(self, x, y):
        """Handle clicks on the weapons list."""
        weapon_list_x = 10
        weapon_list_y = 80
        weapon_list_height = self.height - 200  # Leave space for declarations and buttons
        
        if not (weapon_list_y <= y <= weapon_list_y + weapon_list_height):
            return False
        
        # Calculate which weapon was clicked
        relative_y = y - weapon_list_y + self.scroll_offset
        weapon_index = relative_y // 60  # 60 pixels per weapon (matches drawing)
        
        available_weapons = self._get_available_weapons()
        if 0 <= weapon_index < len(available_weapons):
            weapon_info = available_weapons[weapon_index]
            weapon_profile = weapon_info['profile']
            
            # Check if this is a click on the expand/collapse button
            if weapon_info.get('is_group', False):
                # Check if click is on the expand/collapse button area (right side)
                button_x = self.width - 35  # 35 pixels from right edge (matches drawing position)
                weapon_y = weapon_list_y + weapon_index * 60  # 60 pixels per weapon row (matches drawing)
                button_y = weapon_y + 5  # 5 pixels from top of weapon row
                button_size = 20  # 20x20 pixel button
                
                # Check if click is within the button bounds
                if (button_x <= x <= button_x + button_size and 
                    button_y <= y <= button_y + button_size):
                    group_id = weapon_info['group_id']
                    self._toggle_weapon_group_expansion(group_id)
                    logger.info(f"INFO: Toggled weapon group expansion for {weapon_profile.parent_wargear.name}")
                    return True
            
            # Handle individual weapon selection
            if not weapon_info.get('is_group', False):
                weapon_instance = weapon_info.get('weapon_instance', 1)
                
                # Check if weapon can be used and hasn't been declared already
                if self._can_use_weapon(weapon_profile) and not self._is_weapon_already_declared(weapon_profile.parent_wargear, weapon_instance):
                    logger.info(f"INFO: Selected weapon: {weapon_profile.parent_wargear.name} #{weapon_instance}")
                    self.select_weapon_for_targeting(weapon_profile, weapon_instance)
                    return True
                else:
                    logger.error(f"ERROR: Cannot use {weapon_profile.parent_wargear.name} #{weapon_instance} - already declared or unavailable")
            else:
                # Handle grouped weapon selection - all weapons in group target the same enemy
                if self._can_use_weapon(weapon_profile):
                    logger.info(f"INFO: Selected weapon group: {weapon_profile.parent_wargear.name} (x{weapon_info['count']})")
                    self.select_weapon_group_for_targeting(weapon_info)
                    return True
                else:
                    logger.error(f"ERROR: Cannot use weapon group {weapon_profile.parent_wargear.name} - unavailable")
        
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
        content_y = self.title_bar_height if self.draggable else 0
        weapons_x = self.x + 10
        weapons_y = self.y + content_y + 80  # Account for title bar height
        weapons_width = self.width - 20
        weapons_height = 200
        
        if (weapons_x <= x <= weapons_x + weapons_width and 
            weapons_y <= y <= weapons_y + weapons_height):
            # Account for scroll offset in the relative calculation
            relative_y = (y - weapons_y) - self.scroll_offset
            weapon_index = relative_y // 60  # 60 pixels per weapon (matches drawing)
            if 0 <= weapon_index < len(self.available_weapons):
                self.hovered_weapon = weapon_index
    
    def execute_shooting(self):
        """Execute all shooting declarations"""
        if not self.weapon_declarations:
            logger.error("ERROR: No shooting declarations to execute")
            return
        option_id = self._option_id_for_action("confirm")
        if not option_id:
            logger.error("ERROR: Missing decision option for shooting execute")
            return
        payload = {"declarations": self._build_declarations_payload()}
        success, apply_result = self._resolve_decision(option_id, payload)
        self.last_execution_success = bool(success)
        if success:
            logger.info(f"INFO: {self.unit.name} completed shooting phase")
        else:
            errors = list(getattr(apply_result, "errors", ()) or [])
            if any("Formless Horror" in str(err or "") for err in errors):
                logger.info(f"INFO: {self.unit.name} Formless Horror gating prevents current declaration; adjust targets.")
                try:
                    self.available_targets = self._get_available_targets()
                except Exception:
                    pass
                return
            logger.error(f"ERROR: {self.unit.name} failed to execute shooting")
        if self.callback:
            self.callback(bool(success))
        self.hide()

    def _resolve_skip(self):
        option_id = self._option_id_for_action("skip")
        if option_id:
            self._resolve_decision(option_id, {"skipped": True})
        self.last_execution_success = False
        if self.callback:
            self.callback(False)
        self.hide()

    def _resolve_decision(self, option_id: str, payload: dict):
        if not option_id or self.decision_request is None:
            return False, None
        game = None
        if self.game_view is not None:
            game = getattr(self.game_view, "game", None)
        if game is None and self.unit is not None:
            try:
                game = self.unit.get_parent_army().player.game
            except Exception:
                game = None
        if game is None:
            return False, None
        try:
            from ...utility.decision_utils import resolve_decision_value
        except Exception:
            return False, None
        value, apply_result = resolve_decision_value(
            game,
            self.decision_request,
            option_id,
            result_payload=payload,
        )
        return bool(value), apply_result

    def _option_id_for_action(self, action: str) -> str:
        from ..decision_ui_utils import option_id_for_action

        return option_id_for_action(self.decision_request, action)

    def _build_declarations_payload(self):
        try:
            from ...utility.entity_ids import get_entity_id
        except Exception:
            return []
        declarations = []
        for decl in list(self.weapon_declarations or []):
            weapon_profile = decl.get("weapon_profile")
            if weapon_profile is None:
                continue
            wargear = getattr(weapon_profile, "parent_wargear", None)
            if wargear is None:
                continue
            profile_name = self._profile_name_for_wargear(wargear, weapon_profile)
            if not profile_name:
                continue
            target_unit = decl.get("target_unit")
            models = list(decl.get("models") or [])
            model_ids = [get_entity_id(m) for m in models if m is not None]
            if not model_ids:
                continue
            entry = {
                "wargear_id": get_entity_id(wargear),
                "profile_name": profile_name,
                "model_ids": model_ids,
            }
            if target_unit is not None:
                entry["target_unit_id"] = get_entity_id(target_unit)
            else:
                if not bool(getattr(weapon_profile, "is_plasma_warhead", lambda: False)()):
                    continue
            # Linked Fire: add origin unit ID if present
            linked_fire_origin_id = decl.get("linked_fire_origin_unit_id")
            if linked_fire_origin_id is not None:
                entry["linked_fire_origin_unit_id"] = str(linked_fire_origin_id)
                linked_fire_mode = decl.get("linked_fire_mode")
                if linked_fire_mode:
                    entry["linked_fire_mode"] = str(linked_fire_mode)
            fd_models = list(decl.get("firing_deck_source_models") or [])
            if fd_models:
                entry["firing_deck_source_model_ids"] = [get_entity_id(m) for m in fd_models if m is not None]
            declarations.append(entry)
        return declarations

    def _profile_name_for_wargear(self, wargear, profile) -> str:
        if wargear is None or profile is None:
            return ""
        profiles = getattr(wargear, "profiles", {}) or {}
        for name, candidate in profiles.items():
            if candidate is profile:
                return str(name)
        return str(getattr(profile, "name", "") or "")
    
    def draw(self, screen):
        """Draw the shooting declaration dialog"""
        if not self.visible:
            return

        # Draw dialog background using BaseDialog
        self.draw_dialog_background(screen)

        # Draw title bar (draggable)
        title_text = f"Shooting Declaration - {self.unit.name}"
        self.draw_title_bar(screen, title_text)

        # Draw instructions
        instructions = "Select a weapon to target, or click Execute to resolve shooting"
        self.draw_instructions(screen, instructions)

        # Create surface for dialog content (excluding title bar)
        content_y = self.title_bar_height if self.draggable else 0
        content_height = self.height - content_y
        dialog_surface = pygame.Surface((self.width, content_height), pygame.SRCALPHA)

        # Draw weapons and declarations inside their own clipped areas with independent scrolling
        weapons_clip = pygame.Rect(0, 0, self.width, 250)
        decl_clip = pygame.Rect(0, 300, self.width, content_height - 360)
        prev_clip = dialog_surface.get_clip()
        dialog_surface.set_clip(weapons_clip)
        self._draw_weapons_list(dialog_surface, self.font_medium, self.font_small)
        dialog_surface.set_clip(decl_clip)
        self._draw_declarations_list(dialog_surface, self.font_medium, self.font_small)
        dialog_surface.set_clip(prev_clip)

        # Draw buttons using BaseDialog
        self.draw_button(screen, 'execute', "Execute Shooting")
        self.draw_button(screen, 'cancel', "Cancel")

        # Draw content on screen
        screen.blit(dialog_surface, (self.x, self.y + content_y))
    
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
            if getattr(weapon_profile, "is_bubblechukka", lambda: False)():
                weapon_name += " (random profile)"
            elif weapon_profile.name != 'default':
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
            target_unit = declaration.get('target_unit')
            if target_unit is None:
                target_name = "Deathstrike marker"
            else:
                target_name = target_unit.name[:15] + "..." if len(target_unit.name) > 15 else target_unit.name
            declaration_text = f"{weapon_name} -> {target_name}"
            text_surface = font_small.render(declaration_text, True, self.text_color)
            screen.blit(text_surface, (x + 5, declaration_y + 5))
    


    def select_weapon_for_targeting(self, weapon_profile, weapon_instance=1):
        """Select a weapon and enter targeting mode"""
        logger.info(f"INFO: select_weapon_for_targeting called with {weapon_profile.parent_wargear.name} #{weapon_instance}")

        if not self._can_add_ctan_power_weapon(weapon_profile):
            self._show_ctan_limit_error()
            return

        # Plasma Warhead: no target selection, resolve from marker
        if hasattr(weapon_profile, 'is_plasma_warhead') and weapon_profile.is_plasma_warhead():
            self._add_plasma_warhead_declaration(weapon_profile, weapon_instance=weapon_instance)
            return

        # Check if weapon has Linked Fire - if so, open origin selection dialog
        if hasattr(weapon_profile, 'is_linked_fire') and weapon_profile.is_linked_fire():
            self._open_linked_fire_origin_dialog(weapon_profile, weapon_instance)
            return

        self.selected_weapon = weapon_profile
        self.selected_weapon_instance = weapon_instance
        self.selected_weapon_group = None
        self.is_targeting_mode = True
        self.visible = False  # Close dialog

        # Set weapon profile on game view for range visualization
        if hasattr(self, 'game_view') and self.game_view:
            self.game_view.selected_weapon_profile = weapon_profile

        logger.info(f"INFO: Targeting mode set: is_targeting_mode={self.is_targeting_mode}, selected_weapon={self.selected_weapon}")
        logger.info(f"INFO: Selected {weapon_profile.parent_wargear.name} #{weapon_instance} for targeting - click on battlefield")
    
    def select_weapon_group_for_targeting(self, weapon_group_info):
        """Select a weapon group and enter targeting mode"""
        logger.info(f"INFO: select_weapon_group_for_targeting called with {weapon_group_info['profile'].parent_wargear.name} (x{weapon_group_info['count']})")
        if not self._can_add_ctan_power_weapon(weapon_group_info['profile']):
            self._show_ctan_limit_error()
            return
        if hasattr(weapon_group_info['profile'], 'is_plasma_warhead') and weapon_group_info['profile'].is_plasma_warhead():
            self._add_plasma_warhead_group_declarations(weapon_group_info)
            return
        self.selected_weapon = weapon_group_info['profile']
        self.selected_weapon_group = weapon_group_info
        self.selected_weapon_instance = None
        self.is_targeting_mode = True
        self.visible = False  # Close dialog

        # Set weapon profile on game view for range visualization
        if hasattr(self, 'game_view') and self.game_view:
            self.game_view.selected_weapon_profile = weapon_group_info['profile']

        logger.info(f"INFO: Targeting mode set: is_targeting_mode={self.is_targeting_mode}, selected_weapon_group={self.selected_weapon_group}")
        logger.info(f"INFO: Selected weapon group {weapon_group_info['profile'].parent_wargear.name} (x{weapon_group_info['count']}) for targeting - click on battlefield")

    def _build_valid_targets_cache(self):
        # Deprecated: no precomputation to keep targeting responsive
        return
    
    def handle_battlefield_targeting(self, x: float, y: float) -> bool:
        """Handle clicking on the battlefield for targeting."""
        if not self.selected_weapon:
            logger.error("ERROR: No weapon selected for targeting")
            return False
            
        # Auto-target support (e.g., FIRE OVERWATCH): if force_single_target_unit is set, use it
        if hasattr(self, 'force_single_target_unit') and self.force_single_target_unit is not None:
            clicked_unit = self.force_single_target_unit
        else:
            # Get clicked unit using game view's unit detection
            clicked_unit = None
            if self.game_view:
                clicked_unit = self.game_view.get_unit_at_position(x, y, needs_conversion=False)
        
        if not clicked_unit:
            logger.error("ERROR: No unit found at clicked position")
            try:
                if self.game_view is not None:
                    self.game_view._mission_popup = {
                        "title": "Targeting",
                        "body": "No unit found at that position.",
                    }
            except Exception:
                pass
            return False

        # Validate only on the specific clicked model for clarity and speed
        clicked_model = None
        if self.game_view and hasattr(self.game_view, 'get_model_at_position'):
            # x,y are game coords in targeting mode (BattlePhaseHandler converts before calling us)
            clicked_model = self.game_view.get_model_at_position(x, y, needs_conversion=False)
        weapon_name = self._get_weapon_display_name(self.selected_weapon)
        valid, reason = self._validate_click_target_with_reason(self.selected_weapon, clicked_unit, clicked_model)
        if not valid:
            suffix = f" - {reason}" if reason else ""
            logger.error(f"ERROR: {clicked_unit.name} is not a valid target for {weapon_name}{suffix}")
            try:
                if self.game_view is not None:
                    self.game_view._mission_popup = {
                        "title": "Invalid target",
                        "body": f"{clicked_unit.name} is not a valid target for {weapon_name}.\n{reason or ''}".strip(),
                    }
            except Exception:
                pass
            return False

        # Handle weapon group targeting
        if self.selected_weapon_group:
            # Create individual declarations for each weapon instance in the group
            for weapon_info in self.selected_weapon_group['individual_weapons']:
                decl = {
                    'weapon_profile': self.selected_weapon,
                    'target_unit': clicked_unit,
                    'models': [weapon_info['model']],  # Single model per declaration
                    'weapon_instance': weapon_info['weapon_instance']
                }
                origin_id, origin_mode = self._current_origin_override()
                if origin_id is not None:
                    decl['linked_fire_origin_unit_id'] = origin_id
                    decl['linked_fire_mode'] = origin_mode
                # Firing Deck: preserve source embarked model(s) for marking as shot during resolution.
                try:
                    sources = getattr(self.unit, "_firing_deck_virtual_sources", {}) or {}
                    weapon_id = getattr(self.selected_weapon, "id", None)
                    if weapon_id and weapon_id in sources:
                        decl["firing_deck_source_models"] = list(sources[weapon_id] or [])
                except Exception:
                    pass
                self.weapon_declarations.append(decl)
            logger.info(f"INFO: {self.unit.name} targeting {clicked_unit.name} with {self.selected_weapon.parent_wargear.name} group (x{self.selected_weapon_group['count']})")
            try:
                from ...utility.event_bus import append_action
                player = self.unit.get_parent_army().player
                append_action(player, f"{self.unit.name} targets {clicked_unit.name} with {self.selected_weapon.parent_wargear.name} (x{self.selected_weapon_group['count']})")
            except Exception:
                pass
        else:
            # Handle individual weapon targeting
            weapon_instance = getattr(self, 'selected_weapon_instance', 1)

            # For individual weapon instances, assign only one model per declaration
            # This ensures each weapon instance fires once, not once per model
            assigned_model = self._get_model_for_weapon_instance(self.selected_weapon, weapon_instance)

            decl = {
                'weapon_profile': self.selected_weapon,
                'target_unit': clicked_unit,
                'models': assigned_model,
                'weapon_instance': weapon_instance
            }
            origin_id, origin_mode = self._current_origin_override()
            if origin_id is not None:
                decl['linked_fire_origin_unit_id'] = origin_id
                decl['linked_fire_mode'] = origin_mode
            # Firing Deck: preserve source embarked model(s) for marking as shot during resolution.
            try:
                sources = getattr(self.unit, "_firing_deck_virtual_sources", {}) or {}
                weapon_id = getattr(self.selected_weapon, "id", None)
                if weapon_id and weapon_id in sources:
                    decl["firing_deck_source_models"] = list(sources[weapon_id] or [])
            except Exception:
                pass
            self.weapon_declarations.append(decl)
            logger.error(f"ERROR: {self.unit.name} targeting {clicked_unit.name} with {self.selected_weapon.parent_wargear.name} #{weapon_instance} (assigned to {assigned_model[0].name if assigned_model else 'no model'})")
            try:
                from ...utility.event_bus import append_action
                player = self.unit.get_parent_army().player
                append_action(player, f"{self.unit.name} targets {clicked_unit.name} with {self.selected_weapon.parent_wargear.name} #{weapon_instance}")
            except Exception:
                pass
        
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
            self._linked_fire_origin_unit_id = None  # Clear Linked Fire state
            self.visible = True  # Reopen dialog

    def _current_origin_override(self):
        """Return (origin_unit_id, mode) for current targeting selection."""
        if getattr(self, "_linked_fire_origin_unit_id", None) is not None:
            return self._linked_fire_origin_unit_id, "linked_fire"
        if getattr(self, "_infernal_puppeteer_origin_unit_id", None) is not None:
            return self._infernal_puppeteer_origin_unit_id, "infernal_puppeteer"
        return None, None

    def _add_plasma_warhead_declaration(self, weapon_profile, *, weapon_instance=1):
        """Add a Plasma Warhead declaration without selecting a target."""
        assigned_model = self._get_model_for_weapon_instance(weapon_profile, weapon_instance)
        if not assigned_model:
            logger.error("ERROR: Plasma Warhead: no model assigned")
            return
        decl = {
            'weapon_profile': weapon_profile,
            'target_unit': None,
            'models': assigned_model,
            'weapon_instance': weapon_instance,
        }
        self.weapon_declarations.append(decl)
        logger.info(f"INFO: {self.unit.name} declared Plasma Warhead (marker-based) with {weapon_profile.parent_wargear.name} #{weapon_instance}")
        self.visible = True

    def _add_plasma_warhead_group_declarations(self, weapon_group_info):
        """Add Plasma Warhead declarations for each weapon instance in a group."""
        for weapon_info in weapon_group_info['individual_weapons']:
            decl = {
                'weapon_profile': weapon_group_info['profile'],
                'target_unit': None,
                'models': [weapon_info['model']],
                'weapon_instance': weapon_info['weapon_instance'],
            }
            self.weapon_declarations.append(decl)
        logger.info(f"INFO: {self.unit.name} declared Plasma Warhead group (x{weapon_group_info['count']})")
        self.visible = True

    def _has_infernal_puppeteer(self) -> bool:
        sr = getattr(self.unit, "special_rules", None)
        return bool(isinstance(sr, dict) and sr.get("enhancement_infernal_puppeteer"))

    def _maybe_prompt_infernal_puppeteer_origin(self) -> None:
        if self.unit is None or self._infernal_puppeteer_origin_chosen:
            return
        if not self._has_infernal_puppeteer():
            return
        self._open_infernal_puppeteer_origin_dialog()

    def _open_infernal_puppeteer_origin_dialog(self):
        """Open dialog to select Infernal Puppeteer origin unit."""
        if self.unit is None:
            return
        logger.info(f"INFO: Opening Infernal Puppeteer origin selection for {self.unit.name}")

        from ...rules.enhancement_descriptors import get_enhancement_tool_descriptor
        desc = get_enhancement_tool_descriptor(enhancement_id="000009810003", name="Infernal Puppeteer")
        try:
            range_in = float(getattr(desc, "range_in", 9.0) or 9.0)
        except Exception:
            range_in = 9.0

        from ...utility.aura_utils import get_eligible_infernal_puppeteer_origin_units
        eligible_units = get_eligible_infernal_puppeteer_origin_units(self.unit, game_map=self.game_map, range_in=range_in)

        if not eligible_units:
            self._infernal_puppeteer_origin_chosen = True
            self._infernal_puppeteer_origin_unit_id = None
            return

        def on_confirm(origin_unit_id):
            """Handle Infernal Puppeteer origin selection."""
            self._infernal_puppeteer_origin_unit_id = origin_unit_id
            self._infernal_puppeteer_origin_chosen = True
            if origin_unit_id is None:
                logger.info("INFO: Infernal Puppeteer: using bearer position")
            else:
                logger.info(f"INFO: Infernal Puppeteer: using origin unit {origin_unit_id}")

        def on_cancel():
            """Treat cancel as skipping the optional selection."""
            self._infernal_puppeteer_origin_unit_id = None
            self._infernal_puppeteer_origin_chosen = True

        from .linked_fire_origin_dialog import LinkedFireOriginDialog
        if not hasattr(self, "_infernal_puppeteer_dialog"):
            self._infernal_puppeteer_dialog = LinkedFireOriginDialog(self.screen_width, self.screen_height)

        header = f"Select origin for {self.unit.name} (Infernal Puppeteer)"
        subtitle = f"Choose a friendly TZEENTCH LEGIONES DAEMONICA unit within {int(range_in)}\"."
        self._infernal_puppeteer_dialog.show(
            title="Infernal Puppeteer Origin",
            header=header,
            subtitle=subtitle,
            eligible_units=eligible_units,
            none_label="None (use bearer)",
            none_description="Do not use Infernal Puppeteer; measure from bearer.",
            unit_description="Measure range/LOS from this unit.",
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )

        if hasattr(self, 'game_view') and self.game_view and hasattr(self.game_view, 'dialog_manager'):
            try:
                self.game_view.dialog_manager.open(self._infernal_puppeteer_dialog, modal=True)
            except Exception as e:
                logger.exception(f"ERROR: Failed to open Infernal Puppeteer dialog: {e}")
                on_cancel()

    def _open_linked_fire_origin_dialog(self, weapon_profile, weapon_instance=1):
        """Open dialog to select Linked Fire origin unit."""
        logger.info(f"INFO: Opening Linked Fire origin selection for {weapon_profile.parent_wargear.name}")

        # Get eligible Fire Prism units
        from ...utility.aura_utils import get_eligible_linked_fire_origin_units
        eligible_units = get_eligible_linked_fire_origin_units(self.unit, game_map=self.game_map)

        # Store weapon selection for after dialog closes
        self._pending_linked_fire_weapon = weapon_profile
        self._pending_linked_fire_instance = weapon_instance

        def on_confirm(origin_unit_id):
            """Handle Linked Fire origin selection."""
            # Store the origin unit ID for this weapon
            self._linked_fire_origin_unit_id = origin_unit_id

            # Continue to normal targeting mode
            self.selected_weapon = self._pending_linked_fire_weapon
            self.selected_weapon_instance = self._pending_linked_fire_instance
            self.selected_weapon_group = None
            self.is_targeting_mode = True
            self.visible = False

            # Set weapon profile on game view for range visualization
            if hasattr(self, 'game_view') and self.game_view:
                self.game_view.selected_weapon_profile = self._pending_linked_fire_weapon

            if origin_unit_id is None:
                logger.info(f"INFO: Linked Fire: using bearer position (normal Attacks)")
            else:
                logger.info(f"INFO: Linked Fire: using origin unit {origin_unit_id} (Attacks=1)")

            logger.info(f"INFO: Selected {self._pending_linked_fire_weapon.parent_wargear.name} #{self._pending_linked_fire_instance} for targeting - click on battlefield")

        def on_cancel():
            """Handle Linked Fire dialog cancel."""
            self._pending_linked_fire_weapon = None
            self._pending_linked_fire_instance = None
            self._linked_fire_origin_unit_id = None
            self.visible = True  # Reopen shooting dialog

        # Create and show dialog
        from .linked_fire_origin_dialog import LinkedFireOriginDialog
        if not hasattr(self, '_linked_fire_dialog'):
            self._linked_fire_dialog = LinkedFireOriginDialog(self.screen_width, self.screen_height)

        self._linked_fire_dialog.show(
            title="Linked Fire Origin",
            header=f"Select Fire Prism origin for {weapon_profile.parent_wargear.name}",
            subtitle="Choose 'None' to use bearer position with normal Attacks, or select a Fire Prism to measure from.",
            eligible_units=eligible_units,
            on_confirm=on_confirm,
            on_cancel=on_cancel
        )

        # Open dialog via dialog manager
        if hasattr(self, 'game_view') and self.game_view and hasattr(self.game_view, 'dialog_manager'):
            try:
                self.game_view.dialog_manager.open(self._linked_fire_dialog, modal=True)
            except Exception as e:
                logger.exception(f"ERROR: Failed to open Linked Fire dialog: {e}")
                on_cancel()

            # Clear weapon profile on game view to remove range visualization
            if hasattr(self, 'game_view') and self.game_view:
                self.game_view.selected_weapon_profile = None

            logger.info("INFO: Targeting mode cleared")
