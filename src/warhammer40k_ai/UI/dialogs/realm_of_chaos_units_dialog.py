from __future__ import annotations

from typing import Callable, List, Optional, Dict, Iterable

import pygame

from .base_dialog import BaseDialog, BUTTON_BG, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY, PANEL_BORDER
from warhammer40k_ai.utility.entity_ids import get_entity_id


class RealmOfChaosUnitsDialog(BaseDialog):
    """Dialog for selecting up to two units for The Realm of Chaos (multi-select)."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=680, height=520, draggable=True, center=True)
        self.units: List = []
        self.selected_ids: set[str] = set()
        self.outside_ids: set[str] = set()
        self.skip_selected: bool = False
        self.max_units: int = 2
        self.on_confirm: Optional[Callable[[str, dict], None]] = None
        self.decision_request = None
        self._entries: List[dict] = []
        self._entry_by_button: Dict[str, dict] = {}
        self._confirm_option_id: str = ""
        self._skip_option_id: str = ""
        self.title_text: str = "The Realm of Chaos"
        self.subtitle_text: str = ""
        self.instruction_text: str = "Choose units to place into Strategic Reserves, or select None to skip."

        # Scrolling
        self.scroll_offset = 0
        self.max_scroll = 0

    def show(
        self,
        units: List,
        max_units: int,
        on_confirm: Callable[[str, dict], None],
        *,
        outside_ids: Optional[Iterable[str]] = None,
        decision_request=None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        instruction: Optional[str] = None,
    ) -> None:
        self.units = list(units or [])
        self.max_units = max(1, int(max_units or 1))
        self.selected_ids = set()
        self.skip_selected = False
        self.outside_ids = {str(v) for v in list(outside_ids or []) if v is not None}
        self.on_confirm = on_confirm
        self.decision_request = decision_request
        self.title_text = str(title or "The Realm of Chaos")
        self.subtitle_text = str(subtitle or "")
        self.instruction_text = str(
            instruction or "Choose units to place into Strategic Reserves, or select None to skip."
        )
        self.scroll_offset = 0
        self._entries = []
        self._entry_by_button = {}
        self._resolve_option_ids()
        self._build_entries()
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.units = []
        self.selected_ids = set()
        self.skip_selected = False
        self.outside_ids = set()
        self.max_units = 2
        self.on_confirm = None
        self.decision_request = None
        self._entries = []
        self._entry_by_button = {}
        self._confirm_option_id = ""
        self._skip_option_id = ""
        self.title_text = "The Realm of Chaos"
        self.subtitle_text = ""
        self.instruction_text = "Choose units to place into Strategic Reserves, or select None to skip."
        self.scroll_offset = 0
        self.max_scroll = 0

    def _resolve_option_ids(self) -> None:
        self._confirm_option_id = ""
        self._skip_option_id = ""
        if self.decision_request is None:
            return
        from ..decision_ui_utils import option_entries, first_option_id

        entries = option_entries(self.decision_request)
        for entry in entries:
            payload = dict(entry.get("payload", {}) or {})
            action = str(payload.get("action", "") or "")
            if action == "confirm":
                self._confirm_option_id = entry.get("option_id", "")
            if action == "skip":
                self._skip_option_id = entry.get("option_id", "")
        if not self._confirm_option_id:
            self._confirm_option_id = first_option_id(self.decision_request)

    def _build_entries(self) -> None:
        self._entries = [{"kind": "skip", "label": "None (do not use the stratagem)"}]
        for unit in self.units:
            uname = str(getattr(unit, "name", "") or "Unit")
            label = uname
            if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
                label += " [Embarked]"
            uid = str(get_entity_id(unit))
            if uid in self.outside_ids:
                label += " [Outside Shadow]"
            self._entries.append({"kind": "unit", "unit": unit, "label": label})

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
        self._entry_by_button.clear()

        button_width = self.width - 40
        button_height = 56
        button_spacing = 8
        start_y_rel = self.title_bar_height + 80

        for i, entry in enumerate(self._entries):
            rel_y = start_y_rel + i * (button_height + button_spacing) - self.scroll_offset
            if rel_y + button_height < self.title_bar_height + 60 or rel_y > self.height - 80:
                continue
            name = f"entry_{i}"
            self.add_button(name, 20, rel_y, button_width, button_height, enabled=True)
            self._entry_by_button[name] = entry

        total_height = len(self._entries) * (button_height + button_spacing)
        available_height = self.height - (self.title_bar_height + 150)
        self.max_scroll = max(0, total_height - available_height)

        confirm_width, confirm_height = 160, 40
        rel_x = self.width - confirm_width - 20
        rel_y = self.height - confirm_height - 20
        can_confirm = self._can_confirm()
        self.add_button("confirm", rel_x, rel_y, confirm_width, confirm_height, enabled=can_confirm)

    def _can_confirm(self) -> bool:
        if self.skip_selected:
            return True
        count = len(self.selected_ids)
        if count <= 0:
            return False
        if self.max_units > 0 and count > self.max_units:
            return False
        if self._outside_selected() and count > 1:
            return False
        return True

    def _outside_selected(self) -> bool:
        return any(uid in self.outside_ids for uid in self.selected_ids)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "confirm":
            if not self._can_confirm():
                return True
            if callable(self.on_confirm):
                if self.skip_selected:
                    option_id = self._skip_option_id or self._confirm_option_id
                    payload = {"skipped": True}
                else:
                    option_id = self._confirm_option_id
                    payload = {"unit_ids": list(self.selected_ids)}
                self.on_confirm(option_id, payload)
            self.hide()
            return True

        if button_name in self._entry_by_button:
            entry = self._entry_by_button[button_name]
            kind = entry.get("kind")
            if kind == "skip":
                self.skip_selected = True
                self.selected_ids.clear()
                return True
            unit = entry.get("unit")
            if unit is None:
                return True
            uid = str(get_entity_id(unit))
            if uid in self.selected_ids:
                self.selected_ids.remove(uid)
            else:
                if uid in self.outside_ids:
                    # Outside Shadow: only one unit can be selected.
                    self.selected_ids = {uid}
                else:
                    if self._outside_selected():
                        self.selected_ids.clear()
                    if self.max_units > 0 and len(self.selected_ids) >= self.max_units:
                        return True
                    self.selected_ids.add(uid)
            self.skip_selected = False
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        subtitle = self.subtitle_text or f"Select up to {self.max_units} unit(s)"
        self.draw_title_bar(screen, self.title_text or "The Realm of Chaos", subtitle=subtitle)

        inst = self.instruction_text or "Choose units to place into Strategic Reserves, or select None to skip."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        count = len(self.selected_ids)
        count_text = f"Selected: {count}/{self.max_units}"
        count_surface = self.font_small.render(count_text, True, TEXT_SECONDARY)
        screen.blit(count_surface, (self.x + 20, self.y + self.title_bar_height + 34))

        for name, button in self.buttons.items():
            if name == "confirm":
                continue
            entry = self._entry_by_button.get(name)
            label = entry.get("label", "") if entry else name
            is_selected = False
            if entry and entry.get("kind") == "skip":
                is_selected = self.skip_selected
            elif entry and entry.get("kind") == "unit":
                unit = entry.get("unit")
                if unit is not None:
                    uid = str(get_entity_id(unit))
                    is_selected = uid in self.selected_ids

            color = BUTTON_SELECTED if is_selected else BUTTON_BG
            rect = button["rect"]
            pygame.draw.rect(screen, color, (self.x + rect.x, self.y + rect.y, rect.width, rect.height))
            pygame.draw.rect(screen, PANEL_BORDER, (self.x + rect.x, self.y + rect.y, rect.width, rect.height), 2)
            text_surface = self.font_medium.render(label, True, TEXT_PRIMARY)
            screen.blit(text_surface, (self.x + rect.x + 10, self.y + rect.y + 16))

        confirm_button = self.buttons.get("confirm")
        if confirm_button:
            rect = confirm_button["rect"]
            enabled = confirm_button.get("enabled", True)
            color = BUTTON_SELECTED if enabled else BUTTON_BG
            pygame.draw.rect(screen, color, (self.x + rect.x, self.y + rect.y, rect.width, rect.height))
            pygame.draw.rect(screen, PANEL_BORDER, (self.x + rect.x, self.y + rect.y, rect.width, rect.height), 2)
            label = "Confirm"
            text_color = TEXT_PRIMARY if enabled else TEXT_SECONDARY
            text_surface = self.font_medium.render(label, True, text_color)
            text_rect = text_surface.get_rect(center=(self.x + rect.x + rect.width / 2, self.y + rect.y + rect.height / 2))
            screen.blit(text_surface, text_rect)
