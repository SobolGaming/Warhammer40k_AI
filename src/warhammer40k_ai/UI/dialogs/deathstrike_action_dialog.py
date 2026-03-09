"""
Deathstrike Missile Action Dialog

Allows the player to choose between:
- Designate Target (place marker)
- Adjust Target (move marker)
- None (skip action)

If Designate or Adjust is chosen, opens a battlefield point picker to select the marker position.
"""

from __future__ import annotations
from typing import Callable, Optional

import pygame

from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ERROR, BUTTON_BG, BUTTON_HOVER
from .battlefield_point_pick_dialog import BattlefieldPointPickDialog
from ...engine.ui_decision_bridge import (
    queue_decision_request as _queue_decision_request,
)
import logging
logger = logging.getLogger(__name__)


class DeathstrikeActionDialog(BaseDialog):
    """
    Dialog for choosing Deathstrike Missile action (Designate/Adjust/None).
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=500, height=350, draggable=True, center=True)
        
        self.unit = None
        self.game_view = None
        self.on_complete: Optional[Callable] = None
        self.deathstrike_mgr = None
        
        # Action state
        self.selected_action = None  # 'designate', 'adjust', or 'none'
        self.can_designate = False
        self.can_adjust = False
        self.designate_reason = ""
        self.adjust_reason = ""
    
    def show(self, *, unit, game_view, on_complete: Optional[Callable] = None):
        """Show the Deathstrike action dialog."""
        super().show()
        
        self.unit = unit
        self.game_view = game_view
        self.on_complete = on_complete
        
        # Get Deathstrike manager
        army = unit.get_parent_army()
        self.deathstrike_mgr = getattr(army, "deathstrike", None)

        if self.deathstrike_mgr is None or not bool(getattr(unit, "has_plasma_warhead_weapon", lambda: False)()):
            logger.error("ERROR: Deathstrike: No manager found")
            self.hide()
            return
        
        # Check eligibility for each action
        from ...utility.entity_ids import get_entity_id
        unit_id = get_entity_id(unit)
        
        self.can_designate, self.designate_reason = self.deathstrike_mgr.can_designate_target(unit_id)
        self.can_adjust, self.adjust_reason = self.deathstrike_mgr.can_adjust_target(unit_id)
        
        # Create buttons
        self._create_dialog_buttons()
        
        logger.info(f"🎯 Deathstrike Action Dialog shown for {unit.name}")
        logger.info(f"   Can Designate: {self.can_designate} ({self.designate_reason})")
        logger.info(f"   Can Adjust: {self.can_adjust} ({self.adjust_reason})")
    
    def _create_dialog_buttons(self):
        """Create action buttons."""
        self.clear_buttons()
        
        # Designate Target button
        self.add_button('designate', 20, 100, 200, 40)
        
        # Adjust Target button
        self.add_button('adjust', 20, 150, 200, 40)
        
        # None (Skip) button
        self.add_button('none', 20, 200, 200, 40)
        
        # Cancel button
        self.add_button('cancel', self.width - 120, self.height - 50, 100, 35)
    
    def _handle_button_click(self, button_name: str) -> bool:
        """Handle button clicks."""
        if button_name == 'cancel':
            self.hide()
            return True
        elif button_name == 'designate':
            return self._handle_designate()
        elif button_name == 'adjust':
            return self._handle_adjust()
        elif button_name == 'none':
            return self._handle_none()
        return False
    
    def _handle_designate(self) -> bool:
        """Handle Designate Target action."""
        if not self.can_designate:
            logger.error(f"❌ Cannot Designate Target: {self.designate_reason}")
            return False
        
        self._open_point_picker('designate')
        return True
    
    def _handle_adjust(self) -> bool:
        """Handle Adjust Target action."""
        if not self.can_adjust:
            logger.error(f"❌ Cannot Adjust Target: {self.adjust_reason}")
            return False
        
        self._open_point_picker('adjust')
        return True
    
    def _handle_none(self) -> bool:
        """Handle None (skip) action."""
        logger.info("ℹ️ Deathstrike: No action taken")
        
        # Create and resolve decision
        self._create_and_resolve_decision('none', None)
        
        self.hide()
        if self.on_complete:
            self.on_complete()
        return True
    
    def _open_point_picker(self, action: str):
        """Open battlefield point picker for Designate or Adjust."""
        if not hasattr(self.game_view, "battlefield_point_pick_dialog") or self.game_view.battlefield_point_pick_dialog is None:
            self.game_view.battlefield_point_pick_dialog = BattlefieldPointPickDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height()
            )
        
        picker = self.game_view.battlefield_point_pick_dialog
        
        def _validate(x: float, y: float) -> dict:
            """Validate marker position (basic bounds check)."""
            try:
                w = float(getattr(self.game_view.game.map, "width", 60))
                h = float(getattr(self.game_view.game.map, "height", 44))
            except Exception:
                w, h = 60.0, 44.0
            
            if x < 0 or y < 0 or x > w or y > h:
                return {"valid": False, "reason": "Position must be on the battlefield"}
            return {"valid": True, "reason": "OK"}

        def _confirm(pt):
            """Confirm marker placement/movement."""
            x, y = pt
            position = (float(x), float(y))

            # Create and resolve decision
            self._create_and_resolve_decision(action, position)

            logger.info(f"✅ Deathstrike marker {action}d at ({x:.1f}\", {y:.1f}\")")
            self.hide()
            if self.on_complete:
                self.on_complete()

        title = "Designate Target" if action == 'designate' else "Adjust Target"
        instructions = "Click the battlefield to place the Deathstrike marker." if action == 'designate' else "Click the battlefield to move the Deathstrike marker."

        picker.show(
            game_view=self.game_view,
            title=title,
            instructions=instructions,
            validate_cb=_validate,
            on_confirm=_confirm,
            on_cancel=lambda: None,
        )

        try:
            self.game_view.dialog_manager.open(picker, modal=True)
        except Exception:
            pass

    def _create_and_resolve_decision(self, action: str, position: Optional[tuple]):
        """Create and resolve a Deathstrike action decision."""
        from ...engine.decision_kinds import DECISION_DEATHSTRIKE_ACTION
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...engine.decision_dispatcher import resolve_decision_value
        from ...utility.entity_ids import get_entity_id

        game = self.game_view.game
        unit_id = get_entity_id(self.unit)

        # Create decision request
        options = [
            DecisionOption.create(
                f"{action.capitalize()} Target",
                payload={"action": action}
            )
        ]

        req = _queue_decision_request(game,
            DECISION_DEATHSTRIKE_ACTION,
            f"Deathstrike Missile action for {self.unit.name}",
            player_id=getattr(game.get_current_player(), "id", None),
            options=options,
            context={"unit_id": unit_id},
        )

        # Resolve decision
        result_payload = {}
        if position is not None:
            result_payload["position"] = position

        resolve_decision_value(game, req, options[0].option_id, result_payload=result_payload)

    def draw(self, screen: pygame.Surface):
        """Draw the dialog."""
        if not self.visible:
            return

        # Draw dialog background
        self.draw_dialog_background(screen)

        # Draw title bar
        self.draw_title_bar(screen, "Deathstrike Missile Action")

        # Draw instructions
        instructions = "Choose an action for the Deathstrike Missile:"
        self.draw_instructions(screen, instructions)

        # Draw action descriptions
        y_offset = 100

        # Designate Target
        designate_text = "Designate Target (Place Marker)"
        designate_color = TEXT_PRIMARY if self.can_designate else TEXT_ERROR
        text_surface = self.font_medium.render(designate_text, True, designate_color)
        screen.blit(text_surface, (self.x + 240, self.y + y_offset + 10))
        if not self.can_designate:
            reason_surface = self.font_small.render(self.designate_reason, True, TEXT_ERROR)
            screen.blit(reason_surface, (self.x + 240, self.y + y_offset + 30))

        # Adjust Target
        y_offset += 50
        adjust_text = "Adjust Target (Move Marker)"
        adjust_color = TEXT_PRIMARY if self.can_adjust else TEXT_ERROR
        text_surface = self.font_medium.render(adjust_text, True, adjust_color)
        screen.blit(text_surface, (self.x + 240, self.y + y_offset + 10))
        if not self.can_adjust:
            reason_surface = self.font_small.render(self.adjust_reason, True, TEXT_ERROR)
            screen.blit(reason_surface, (self.x + 240, self.y + y_offset + 30))

        # None
        y_offset += 50
        none_text = "None (Skip Action)"
        text_surface = self.font_medium.render(none_text, True, TEXT_PRIMARY)
        screen.blit(text_surface, (self.x + 240, self.y + y_offset + 10))

        # Draw buttons
        self.draw_button(screen, 'designate', "Designate", disabled=not self.can_designate)
        self.draw_button(screen, 'adjust', "Adjust", disabled=not self.can_adjust)
        self.draw_button(screen, 'none', "None")
        self.draw_button(screen, 'cancel', "Cancel")
