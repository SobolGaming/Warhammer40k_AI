import pygame
from typing import List
from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, BUTTON_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED


class MovementChoiceDialog(BaseDialog):
    """Dialog for choosing movement option for a unit during movement phase"""
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=290, draggable=True, center=True)
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_actions = []
        self._embark_candidates = []
    
    def show(self, unit, callback, game_map=None):
        """Show the dialog for the given unit"""
        self.unit = unit
        self.callback = callback
        self.game_map = game_map
        super().show(callback)
        
        # Get available actions based on engagement state
        if game_map:
            engagement_state = unit.get_engagement_state(game_map)
            self.available_actions = unit.get_available_move_actions(engagement_state.value)
        else:
            # Fallback - assume all actions available
            from warhammer40k_ai.units.unit import MovementAction
            self.available_actions = [
                MovementAction.REMAIN_STATIONARY.value,
                MovementAction.MOVE.value,
                MovementAction.ADVANCE.value,
                MovementAction.FALL_BACK.value
            ]
        # Precompute embark candidates if this is a transport
        self._embark_candidates = self._compute_embark_candidates()
        # Create buttons
        self._create_buttons()
    
    def hide(self):
        """Hide the dialog"""
        super().hide()
        self.unit = None
        self.callback = None
        self.game_map = None
        self.available_actions = []
        self._embark_candidates = []

    def is_action_available(self, action_name: str) -> bool:
        """Check if a movement action is available for the current unit"""
        from warhammer40k_ai.units.unit import MovementAction
        
        action_map = {
            'move': MovementAction.MOVE.value,
            'advance': MovementAction.ADVANCE.value,
            'fall_back': MovementAction.FALL_BACK.value,
            'stationary': MovementAction.REMAIN_STATIONARY.value
        }
        
        # Transport-only actions
        if action_name == 'embark':
            return bool(getattr(self.unit, "is_transport", False)) and bool(self._embark_candidates)
        if action_name == 'disembark':
            return bool(getattr(self.unit, "is_transport", False)) and bool(getattr(self.unit, "transport_passengers", []) or [])
        
        if action_name not in action_map:
            return False
            
        return action_map[action_name] in self.available_actions
    
    def handle_event(self, event):
        """Handle pygame events"""
        if not self.visible:
            return False
        # Base handling (drag/ESC/buttons)
        if super().handle_event(event):
            return True
        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m and self.is_action_available('move'):
                if self.callback:
                    self.callback('move')
                self.hide(); return True
            if event.key == pygame.K_a and self.is_action_available('advance'):
                if self.callback:
                    self.callback('advance')
                self.hide(); return True
            if event.key == pygame.K_f and self.is_action_available('fall_back'):
                if self.callback:
                    self.callback('fall_back')
                self.hide(); return True
            if event.key == pygame.K_s and self.is_action_available('stationary'):
                if self.callback:
                    self.callback('stationary')
                self.hide(); return True
            if event.key == pygame.K_e and self.is_action_available('embark'):
                if self.callback:
                    self.callback('embark')
                self.hide(); return True
            if event.key == pygame.K_d and self.is_action_available('disembark'):
                if self.callback:
                    self.callback('disembark')
                self.hide(); return True
        return False

    def _compute_embark_candidates(self) -> List:
        """Return friendly units on the map that are currently valid to embark into this transport."""
        if not self.unit or not getattr(self.unit, "is_transport", False):
            return []
        if not self.game_map:
            return []
        transport = self.unit
        if not getattr(transport, "models", None):
            return []
        try:
            t_model = transport.models[0]
        except Exception:
            return []
        if not getattr(t_model, "is_alive", False):
            return []

        candidates = []
        for u in list(getattr(self.game_map, "units", []) or []):
            if u is None or u == transport:
                continue
            if not u.is_alive():
                continue
            # Must be friendly
            if u.get_parent_army() != transport.get_parent_army():
                continue
            # Must be able to transport (capacity + keyword restrictions)
            if not transport.can_transport(u):
                continue
            # Must have moved (not remain stationary) and not have disembarked this turn
            if getattr(u.round_state, "remained_stationary_this_round", False):
                continue
            if getattr(u.round_state, "disembarked_this_round", False):
                continue
            # Must be within 3" with all models
            ok = True
            from ...utility.aura_utils import distance_between_models_bases_3d
            for m in u.models:
                if not m.is_alive:
                    continue
                if float(distance_between_models_bases_3d(m, t_model)) > 3.0 + 1e-6:
                    ok = False
                    break
            if not ok:
                continue
            candidates.append(u)
        return candidates

    def _create_buttons(self):
        # Clear existing movement buttons
        names = [k for k in self.buttons.keys()]
        for k in names:
            self.buttons.pop(k, None)
            self.button_states.pop(k, None)

        # Layout
        button_width = 110
        button_height = 36
        spacing = 12
        start_x = 20
        y = self.title_bar_height + 78

        self.add_button('move', start_x + 0*(button_width+spacing), y, button_width, button_height, enabled=self.is_action_available('move'))
        self.add_button('advance', start_x + 1*(button_width+spacing), y, button_width, button_height, enabled=self.is_action_available('advance'))
        self.add_button('fall_back', start_x + 2*(button_width+spacing), y, button_width, button_height, enabled=self.is_action_available('fall_back'))
        self.add_button('stationary', start_x + 3*(button_width+spacing), y, button_width, button_height, enabled=self.is_action_available('stationary'))

        # Transport actions row
        if getattr(self.unit, "is_transport", False):
            y2 = y + button_height + 14
            self.add_button('embark', start_x + 0*(button_width+spacing), y2, button_width*2 + spacing, button_height, enabled=self.is_action_available('embark'))
            self.add_button('disembark', start_x + 2*(button_width+spacing), y2, button_width*2 + spacing, button_height, enabled=self.is_action_available('disembark'))

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name in ('move','advance','fall_back','stationary','embark','disembark') and self.is_action_available(button_name):
            if self.callback:
                self.callback(button_name)
            self.hide()
            return True
        return False

    def draw(self, screen):
        """Draw the dialog"""
        if not self.visible or not self.unit:
            return
        
        # Background and title
        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, f"Move {self.unit.name}")

        # Text block under title: consistent left alignment and spacing
        content_x = self.x + 20
        cur_y = self.y + self.title_bar_height + 12

        movement_val = getattr(self.unit.models[0], 'movement', getattr(self.unit, 'movement', 0))
        info_text = f"Movement: {movement_val}\""
        info_surface = self.font_small.render(info_text, True, TEXT_SECONDARY)
        screen.blit(info_surface, (content_x, cur_y))
        cur_y += self.font_small.get_linesize() + 6

        if getattr(self.unit, "is_transport", False):
            try:
                cap = int(getattr(self.unit, "transport_capacity", 0) or 0)
                used = int(getattr(self.unit, "transport_slots_used", 0) or 0)
                passengers = len(getattr(self.unit, "transport_passengers", []) or [])
                tinfo = f"Transport: {used}/{cap} slots | Passengers: {passengers}"
                t_surface = self.font_small.render(tinfo, True, TEXT_SECONDARY)
                screen.blit(t_surface, (content_x, cur_y))
                cur_y += self.font_small.get_linesize() + 6
            except Exception:
                pass

        # Draw buttons
        self._create_buttons()  # refresh enabled state/positions
        for name, rect in self.buttons.items():
            if name in ('move','advance','fall_back','stationary','embark','disembark'):
                label = name.replace('_', ' ').title()
                self.draw_button(screen, name, label, color=BUTTON_BG)
        
        # Help
        help_parts = []
        if self.is_action_available('move'):
            help_parts.append("Move: Normal")
        if self.is_action_available('advance'):
            help_parts.append("Advance: +D6\" no shoot")
        if self.is_action_available('fall_back'):
            help_parts.append("Fall Back: Exit combat")
        if self.is_action_available('embark'):
            help_parts.append("Embark: select unit(s)")
        if self.is_action_available('disembark'):
            help_parts.append("Disembark: select passenger(s)")
        if not help_parts:
            help_parts.append("Only Stationary available")
        help_text = " | ".join(help_parts)
        help_surface = self.font_small.render(help_text, True, TEXT_SECONDARY)
        screen.blit(help_surface, (self.x + 20, self.y + self.height - 30))