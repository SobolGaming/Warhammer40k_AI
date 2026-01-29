from __future__ import annotations

from typing import Callable, List, Optional, Dict

import pygame

from .base_dialog import BaseDialog, BUTTON_BG, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY, PANEL_BORDER
from warhammer40k_ai.utility.entity_ids import get_entity_id


class VesselsOfWrathModelsDialog(BaseDialog):
    """Dialog for selecting Vessels of Wrath models (multi-select with optional skip)."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=680, height=520, draggable=True, center=True)
        self.models: List = []
        self.selected_ids: set[str] = set()
        self.skip_selected: bool = False
        self.max_models: int = 0
        self.on_confirm: Optional[Callable[[str, dict], None]] = None
        self.decision_request = None
        self._entries: List[dict] = []
        self._entry_by_button: Dict[str, dict] = {}
        self._confirm_option_id: str = ""
        self._skip_option_id: str = ""

        # Scrolling
        self.scroll_offset = 0
        self.max_scroll = 0

    def show(
        self,
        models: List,
        max_models: int,
        on_confirm: Callable[[str, dict], None],
        *,
        decision_request=None,
    ) -> None:
        self.models = list(models or [])
        self.max_models = max(0, int(max_models or 0))
        if self.max_models <= 0:
            self.max_models = len(self.models)
        self.selected_ids = set()
        self.skip_selected = False
        self.on_confirm = on_confirm
        self.decision_request = decision_request
        self.scroll_offset = 0
        self._entries = []
        self._entry_by_button = {}
        self._resolve_option_ids()
        self._build_entries()
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.models = []
        self.selected_ids = set()
        self.skip_selected = False
        self.max_models = 0
        self.on_confirm = None
        self.decision_request = None
        self._entries = []
        self._entry_by_button = {}
        self._confirm_option_id = ""
        self._skip_option_id = ""
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
        self._entries = [{"kind": "skip", "label": "None (do not select models)"}]
        for model in self.models:
            unit = getattr(model, "parent_unit", None)
            uname = str(getattr(unit, "name", "") or "Unit")
            label = f"{getattr(model, 'name', 'Model')} — {uname}"
            if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
                label += " [Embarked]"
            self._entries.append({"kind": "model", "model": model, "label": label})

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
        if self.max_models > 0 and count > self.max_models:
            return False
        return True

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
                    payload = {"model_ids": list(self.selected_ids)}
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
            model = entry.get("model")
            if model is None:
                return True
            mid = str(get_entity_id(model))
            if mid in self.selected_ids:
                self.selected_ids.remove(mid)
            else:
                if self.max_models > 0 and len(self.selected_ids) >= self.max_models:
                    return True
                self.selected_ids.add(mid)
            self.skip_selected = False
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        subtitle = f"Select up to {self.max_models} model(s)"
        self.draw_title_bar(screen, "Vessels of Wrath", subtitle=subtitle)

        inst = "Choose models to become Vessels of Wrath, or select None to skip."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        count = len(self.selected_ids)
        count_text = f"Selected: {count}/{self.max_models}"
        count_surface = self.font_tiny.render(count_text, True, TEXT_SECONDARY)
        screen.blit(count_surface, (self.x + 20, self.y + self.title_bar_height + 32))

        self._create_buttons()
        self._update_buttons()

        for name, rect in self.buttons.items():
            if name == "confirm":
                continue
            entry = self._entry_by_button.get(name)
            if entry is None:
                continue
            label = entry.get("label", "")
            if entry.get("kind") == "skip":
                selected = self.skip_selected
            else:
                model = entry.get("model")
                mid = str(get_entity_id(model)) if model is not None else ""
                selected = mid in self.selected_ids
            color = BUTTON_SELECTED if selected else BUTTON_BG
            self.draw_button(screen, name, label, color=color)
            pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        if "confirm" in self.buttons:
            self.button_states["confirm"]["enabled"] = self._can_confirm()
            self.draw_button(screen, "confirm", "Confirm")
