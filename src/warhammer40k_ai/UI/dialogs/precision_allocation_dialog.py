import pygame
from typing import List, Optional, Callable

from .base_dialog import BaseDialog, BUTTON_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_SELECTED


class PrecisionAllocationDialog(BaseDialog):
    """
    PRECISION allocation prompt.

    When a PRECISION attack successfully wounds an Attached Unit and at least one CHARACTER model
    in that unit is visible to the attacking model, the attacker may allocate that wound to a
    visible CHARACTER model instead of the normal bodyguard allocation sequence.
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=760, height=420, draggable=True, center=True)
        self.attacker_model = None
        self.target_unit = None
        self.weapon_name = ""
        self.character_models: List = []
        self.choice_model = None  # None means "Bodyguard (normal)"
        self.on_choice: Optional[Callable[[str], None]] = None

        self.scroll_offset = 0
        self.max_scroll = 0
        self.decision_request = None
        self._bodyguard_entry: Optional[dict] = None
        self._character_entries: List[dict] = []

    def show(self, attacker_model, target_unit, weapon_name: str, character_models: List, on_choice: Callable[[str], None], *, decision_request=None) -> None:
        self.attacker_model = attacker_model
        self.target_unit = target_unit
        self.weapon_name = weapon_name or "PRECISION weapon"
        self.character_models = list(character_models or [])
        self.choice_model = None
        self.decision_request = decision_request
        self._bodyguard_entry = None
        self._character_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            entries = option_entries(self.decision_request)
            for entry in entries:
                payload = entry.get("payload", {})
                model_id = payload.get("model_id", payload.get("model"))
                if model_id in (None, "") or str(payload.get("action", "")) == "bodyguard":
                    if self._bodyguard_entry is None:
                        self._bodyguard_entry = entry
                else:
                    self._character_entries.append(entry)
        self.on_choice = on_choice
        self.scroll_offset = 0
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.attacker_model = None
        self.target_unit = None
        self.weapon_name = ""
        self.character_models = []
        self.choice_model = None
        self.on_choice = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self.decision_request = None
        self._bodyguard_entry = None
        self._character_entries = []

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if super().handle_event(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll_offset = max(0, self.scroll_offset - 20)
                return True
            if event.button == 5:
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                return True
        return False

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()

        # Bodyguard option
        if self._bodyguard_entry is not None:
            self.add_button("bodyguard", 20, self.title_bar_height + 70, self.width - 40, 44, enabled=True)

        # Character list
        row_h = 44
        start_y = self.title_bar_height + 130
        visible_h = self.height - (start_y + 70)

        for i, _entry in enumerate(self._character_entries):
            rel_y = start_y + i * row_h - self.scroll_offset
            if rel_y + row_h < start_y or rel_y > start_y + visible_h:
                continue
            self.add_button(f"char_{i}", 20, rel_y, self.width - 40, 44, enabled=True)

        total_h = len(self._character_entries) * row_h
        self.max_scroll = max(0, total_h - visible_h)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "bodyguard" and self._bodyguard_entry is not None:
            self.choice_model = None
            if self.on_choice:
                self.on_choice(self._bodyguard_entry.get("option_id", ""))
            self.hide()
            return True
        if button_name.startswith("char_"):
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            if 0 <= idx < len(self._character_entries):
                entry = self._character_entries[idx]
                if self.on_choice:
                    self.on_choice(entry.get("option_id", ""))
            self.hide()
            return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        self.draw_dialog_background(screen)

        attacker_name = getattr(self.attacker_model, "name", "Attacker")
        target_name = getattr(self.target_unit, "name", "Target")
        subtitle = f"{attacker_name} vs {target_name} ({self.weapon_name})"
        self.draw_title_bar(screen, "PRECISION - Allocate Wound", subtitle=subtitle)

        inst = "Choose allocation for this weapon's remaining wounds:"
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        # Update buttons for scroll
        self._create_buttons()
        self._update_buttons()

        # Bodyguard option
        if self._bodyguard_entry is not None:
            bodyguard_label = str(self._bodyguard_entry.get("label", "Bodyguard (normal allocation)") or "Bodyguard (normal allocation)")
            self.draw_button(screen, "bodyguard", bodyguard_label, color=BUTTON_BG)
            try:
                rect = self.buttons["bodyguard"]
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)
            except Exception:
                pass

        # Characters label
        hdr = self.font_small.render("Visible CHARACTER models:", True, TEXT_PRIMARY)
        screen.blit(hdr, (self.x + 20, self.y + self.title_bar_height + 105))

        for i, entry in enumerate(self._character_entries):
            btn = f"char_{i}"
            if btn not in self.buttons:
                continue
            label = str(entry.get("label", "CHARACTER") or "CHARACTER")
            self.draw_button(screen, btn, label, color=BUTTON_BG)
            pygame.draw.rect(screen, PANEL_BORDER, self.buttons[btn], 1)

        note = "This choice is remembered for the rest of this weapon profile's attacks."
        note_surface = self.font_tiny.render(note, True, TEXT_SECONDARY)
        screen.blit(note_surface, (self.x + 20, self.y + self.height - 40))

