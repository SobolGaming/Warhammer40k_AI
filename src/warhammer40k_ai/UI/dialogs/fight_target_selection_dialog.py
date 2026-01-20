import pygame
from typing import List, Callable, Optional, Dict

from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class FightTargetSelectionDialog(BaseDialog):
    """Dialog for selecting which engaged enemy unit to fight."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=560, height=420, draggable=True, center=True)

        # State
        self.fighting_unit: Optional[Unit] = None
        self.eligible_targets: List[Unit] = []
        self.on_target_selected: Optional[Callable[[str, List[str]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.decision_request = None
        self._option_entries: List[dict] = []
        self._entry_targets: List[tuple] = []

        # Button mapping: name -> Unit
        self._button_to_target: Dict[str, Unit] = {}

    def show(self, fighting_unit: Unit, eligible_targets: List[Unit],
             on_target_selected: Callable[[str, List[str]], None],
             on_cancel: Optional[Callable[[], None]] = None,
             decision_request=None) -> None:
        self.fighting_unit = fighting_unit
        self.eligible_targets = eligible_targets
        self.decision_request = decision_request
        self._option_entries = []
        self._entry_targets = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)
            target_by_id = {get_entity_id(t): t for t in list(eligible_targets or [])}
            for entry in self._option_entries:
                payload = entry.get("payload", {})
                target_id = str(payload.get("target_unit_id", payload.get("unit_id", payload.get("unit", ""))) or "")
                self._entry_targets.append((entry, target_by_id.get(target_id)))
        self.on_target_selected = on_target_selected
        self.on_cancel = on_cancel
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.fighting_unit = None
        self.eligible_targets = []
        self.on_target_selected = None
        self.on_cancel = None
        self._button_to_target.clear()
        self.decision_request = None
        self._option_entries = []
        self._entry_targets = []

    def _create_buttons(self) -> None:
        # Clear any existing buttons
        self.buttons.clear()
        self.button_states.clear()
        self._button_to_target.clear()

        button_width = self.width - 40
        button_height = 70
        button_spacing = 10
        start_y = (self.title_bar_height + 60)  # Below title/instructions

        for i, (entry, target) in enumerate(self._entry_targets):
            rel_x = 20
            rel_y = start_y + i * (button_height + button_spacing)
            name = f"target_{i}"
            self.add_button(name, rel_x, rel_y, button_width, button_height, enabled=True)
            self._button_to_target[name] = target

        # Cancel button (bottom-right)
        cancel_width, cancel_height = 120, 40
        rel_x = self.width - cancel_width - 20
        rel_y = self.height - cancel_height - 20
        self.add_button('cancel', rel_x, rel_y, cancel_width, cancel_height, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == 'cancel':
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name in self._button_to_target:
            target = self._button_to_target[button_name]
            idx = None
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                idx = None
            if self.on_target_selected and idx is not None and 0 <= idx < len(self._entry_targets):
                entry, _unit = self._entry_targets[idx]
                payload = entry.get("payload", {})
                target_ids = payload.get("target_unit_ids")
                if isinstance(target_ids, list):
                    target_ids = [str(val) for val in target_ids if val is not None]
                else:
                    target_id = str(payload.get("target_unit_id", payload.get("unit_id", payload.get("unit", ""))) or "")
                    target_ids = [target_id] if target_id else []
                self.on_target_selected(entry.get("option_id", ""), target_ids)
            self.hide()
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        # Overlay behind the dialog
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        # Dialog background and title bar
        self.draw_dialog_background(screen)
        unit_name = self.fighting_unit.name if self.fighting_unit else "Unit"
        self.draw_title_bar(screen, f"Select Target for {unit_name}")

        # Instructions
        self.draw_instructions(screen, "Choose an engaged enemy unit to fight.")

        # Draw target buttons
        for name, rect in self.buttons.items():
            if name == 'cancel':
                continue
            # Button background with hover handled by BaseDialog.draw_button
            target = self._button_to_target.get(name)
            label = target.name if target else name
            if target is None:
                try:
                    idx = int(name.split("_", 1)[1])
                    entry, _unit = self._entry_targets[idx]
                    label = str(entry.get("label", label) or label)
                except Exception:
                    pass
            # Draw the button
            self.draw_button(screen, name, label, color=BUTTON_BG)

            # Additional status line
            if target:
                models_alive = len([m for m in target.models if m.is_alive])
                status_text = f"Models: {models_alive}"
                status_surface = self.font_small.render(status_text, True, TEXT_SECONDARY)
                screen.blit(status_surface, (rect.x + 12, rect.y + rect.height - 22))

        # Draw cancel button
        self.draw_button(screen, 'cancel', 'Cancel', color=BUTTON_BG)
