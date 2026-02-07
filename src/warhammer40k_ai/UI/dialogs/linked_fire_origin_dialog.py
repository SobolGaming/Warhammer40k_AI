"""
Linked Fire Origin Selection Dialog

Allows the player to choose a Fire Prism unit to use as the origin for range/LOS measurement,
or select "None" to use the bearer's own position.
"""

from __future__ import annotations

from typing import Callable, List, Optional

import pygame

from .base_dialog import (
    BaseDialog,
    PANEL_BG,
    PANEL_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BUTTON_BG,
    BUTTON_HOVER,
    BUTTON_SELECTED,
)


class LinkedFireOriginDialog(BaseDialog):
    """
    Modal dialog to select a Fire Prism unit as Linked Fire origin.
    
    Includes a "None (use bearer)" option to allow normal shooting without Linked Fire.
    """
    
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=640, height=480, draggable=True, center=True)
        self.title = "Linked Fire Origin"
        self.subtitle = ""
        self.header = ""
        self.eligible_units: List = []
        self.selected_idx: Optional[int] = None
        self.none_label = "None (use bearer)"
        self.none_description = "Use normal range/LOS from bearer. Attacks = normal."
        self.unit_description = "Measure range/LOS from this unit. Attacks = 1."
        self._on_confirm: Optional[Callable[[Optional[str]], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None
        
        self.add_button("confirm", 10, self.height - 50, 160, 35)
        self.add_button("cancel", self.width - 160, self.height - 50, 140, 35)
    
    def show(
        self,
        *,
        title: str = "Linked Fire Origin",
        header: str = "",
        subtitle: str = "",
        eligible_units: List = None,
        none_label: Optional[str] = None,
        none_description: Optional[str] = None,
        unit_description: Optional[str] = None,
        on_confirm: Callable[[Optional[str]], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        """
        Show the dialog.
        
        Args:
            title: Dialog title
            header: Header text
            subtitle: Subtitle text
            eligible_units: List of eligible Fire Prism units
            on_confirm: Callback with selected unit_id (None if "None" option selected)
            on_cancel: Callback for cancel action
        """
        super().show()
        self.visible = True
        self.title = title or "Linked Fire Origin"
        self.header = header or ""
        self.subtitle = subtitle or ""
        self.eligible_units = eligible_units or []
        if none_label is not None:
            self.none_label = none_label
        if none_description is not None:
            self.none_description = none_description
        if unit_description is not None:
            self.unit_description = unit_description
        self.selected_idx = 0  # Default to "None" option
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
    
    def hide(self):
        super().hide()
        self.subtitle = ""
        self.header = ""
        self.eligible_units = []
        self.selected_idx = None
        self.none_label = "None (use bearer)"
        self.none_description = "Use normal range/LOS from bearer. Attacks = normal."
        self.unit_description = "Measure range/LOS from this unit. Attacks = 1."
        self._on_confirm = None
        self._on_cancel = None
    
    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self._on_cancel is not None:
                self._on_cancel()
            self.hide()
            return True
        if button_name == "confirm":
            if self.selected_idx is None:
                return True
            
            # Index 0 is "None (use bearer)", indices 1+ are eligible units
            if self.selected_idx == 0:
                # User selected "None" - use bearer
                if self._on_confirm is not None:
                    self._on_confirm(None)
            else:
                # User selected a Fire Prism unit
                unit_idx = self.selected_idx - 1
                if 0 <= unit_idx < len(self.eligible_units):
                    unit = self.eligible_units[unit_idx]
                    from ...utility.entity_ids import get_entity_id
                    unit_id = get_entity_id(unit)
                    if self._on_confirm is not None:
                        self._on_confirm(unit_id)
            
            self.hide()
            return True
        return False
    
    def _handle_dialog_click(self, mouse_pos) -> bool:
        """Handle clicks in the list area to change selection."""
        mx, my = mouse_pos
        rel_x = mx - self.x
        rel_y = my - self.y - (self.title_bar_height if self.draggable else 0)
        
        # List area starts after header
        list_start_y = 80
        list_item_height = 40
        
        if rel_y < list_start_y:
            return False
        
        # Calculate which item was clicked
        item_idx = int((rel_y - list_start_y) / list_item_height)
        total_items = 1 + len(self.eligible_units)  # "None" + eligible units
        
        if 0 <= item_idx < total_items:
            self.selected_idx = item_idx
            return True

        return False

    def draw(self, screen: pygame.Surface):
        """Draw the dialog."""
        if not self.visible:
            return

        # Draw dialog background
        self.draw_dialog_background(screen)

        # Draw title bar
        self.draw_title_bar(screen, self.title)

        # Draw header
        if self.header:
            header_surface = self.font_medium.render(self.header, True, TEXT_PRIMARY)
            screen.blit(header_surface, (self.x + 20, self.y + 50))

        # Draw subtitle
        if self.subtitle:
            subtitle_surface = self.font_small.render(self.subtitle, True, TEXT_SECONDARY)
            screen.blit(subtitle_surface, (self.x + 20, self.y + 70))

        # Draw list of options
        list_start_y = 80
        list_item_height = 40

        # Option 0: "None (use bearer)"
        self._draw_list_item(
            screen,
            0,
            self.none_label,
            self.none_description,
            list_start_y,
            list_item_height
        )

        # Options 1+: Eligible Fire Prism units
        for i, unit in enumerate(self.eligible_units):
            unit_name = getattr(unit, "name", "Unknown Unit")
            description = self.unit_description
            self._draw_list_item(
                screen,
                i + 1,
                unit_name,
                description,
                list_start_y,
                list_item_height
            )

        # Draw buttons
        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")

    def _draw_list_item(self, screen: pygame.Surface, idx: int, name: str, description: str, list_start_y: int, item_height: int):
        """Draw a single list item."""
        y_pos = self.y + list_start_y + (idx * item_height)

        # Background
        is_selected = (idx == self.selected_idx)
        bg_color = BUTTON_SELECTED if is_selected else PANEL_BG
        pygame.draw.rect(screen, bg_color, (self.x + 10, y_pos, self.width - 20, item_height - 2))
        pygame.draw.rect(screen, PANEL_BORDER, (self.x + 10, y_pos, self.width - 20, item_height - 2), 1)

        # Name
        name_surface = self.font_medium.render(name, True, TEXT_PRIMARY)
        screen.blit(name_surface, (self.x + 20, y_pos + 5))

        # Description
        desc_surface = self.font_small.render(description, True, TEXT_SECONDARY)
        screen.blit(desc_surface, (self.x + 20, y_pos + 22))
