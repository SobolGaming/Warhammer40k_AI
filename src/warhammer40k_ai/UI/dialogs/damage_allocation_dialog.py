import pygame
from typing import List, Optional, Callable, Any

from .base_dialog import BaseDialog, BUTTON_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY
from ...utility.entity_ids import get_entity_id


class DamageAllocationDialog(BaseDialog):
    """
    Generic model-pick dialog for damage allocation (defender choice) and similar prompts (e.g., Hazardous).
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=760, height=460, draggable=True, center=True)
        self.unit = None
        self.models: List[Any] = []
        self.entries: List[Optional[Any]] = []
        self.title_text = "Allocate Damage"
        self.subtitle_text = ""
        self.instruction_text = ""
        self.on_choice: Optional[Callable[[str], None]] = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self.include_none = False
        self.none_label = "None"
        self.show_wargear = False
        self.decision_request = None
        self._option_entries: List[dict] = []
        self._entry_models: List[tuple] = []

    def show(
        self,
        unit: Any,
        models: List[Any],
        *,
        title: str,
        subtitle: str = "",
        instruction: str = "",
        on_choice: Callable[[str], None],
        include_none: bool = False,
        none_label: str = "None",
        show_wargear: bool = False,
        decision_request=None,
    ) -> None:
        self.unit = unit
        self.models = list(models or [])
        self.include_none = bool(include_none)
        self.none_label = none_label or "None"
        self.show_wargear = bool(show_wargear)
        self.decision_request = decision_request
        self._option_entries = []
        self._entry_models = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)
            model_by_id = {get_entity_id(m): m for m in list(self.models or [])}
            for entry in self._option_entries:
                payload = entry.get("payload", {})
                model_id = payload.get("model_id", payload.get("model"))
                model = model_by_id.get(str(model_id)) if model_id not in (None, "") else None
                self._entry_models.append((entry, model))
        self.entries = [m for _, m in self._entry_models]
        self.title_text = title or "Allocate Damage"
        self.subtitle_text = subtitle or ""
        self.instruction_text = instruction or ""
        self.on_choice = on_choice
        self.scroll_offset = 0
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.unit = None
        self.models = []
        self.entries = []
        self.on_choice = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self.include_none = False
        self.none_label = "None"
        self.show_wargear = False
        self.decision_request = None
        self._option_entries = []
        self._entry_models = []

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

        row_h = 84 if self.show_wargear else 52
        btn_h = 74 if self.show_wargear else 48
        start_y = self.title_bar_height + 100
        visible_h = self.height - (start_y + 30)

        for i, _m in enumerate(self.entries):
            rel_y = start_y + i * row_h - self.scroll_offset
            if rel_y + row_h < start_y or rel_y > start_y + visible_h:
                continue
            self.add_button(f"m_{i}", 20, rel_y, self.width - 40, btn_h, enabled=True)

        total_h = len(self.entries) * row_h
        self.max_scroll = max(0, total_h - visible_h)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name.startswith("m_"):
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            if 0 <= idx < len(self._entry_models):
                entry, _model = self._entry_models[idx]
                if self.on_choice:
                    self.on_choice(entry.get("option_id", ""))
                self.hide()
                return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        self.draw_dialog_background(screen)

        unit_name = getattr(self.unit, "name", "Unit")
        subtitle = self.subtitle_text or unit_name
        self.draw_title_bar(screen, self.title_text, subtitle=subtitle)

        if self.instruction_text:
            inst_surface = self.font_small.render(self.instruction_text, True, TEXT_SECONDARY)
            screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        # Update buttons for scroll
        self._create_buttons()
        self._update_buttons()

        hdr = self.font_small.render("Select a model:", True, TEXT_PRIMARY)
        screen.blit(hdr, (self.x + 20, self.y + self.title_bar_height + 60))

        for i, (_entry, m) in enumerate(self._entry_models):
            btn = f"m_{i}"
            if btn not in self.buttons:
                continue
            if m is None:
                label = self.none_label
                if self.show_wargear:
                    self.draw_button(screen, btn, "", color=BUTTON_BG)
                    rect = self.buttons[btn]
                    label_surface = self.font_small.render(label, True, TEXT_PRIMARY)
                    screen.blit(label_surface, (rect.x + 12, rect.y + 8))
                else:
                    self.draw_button(screen, btn, label, color=BUTTON_BG)
                pygame.draw.rect(screen, PANEL_BORDER, self.buttons[btn], 1)
                continue
            label = getattr(m, "name", f"Model {i+1}")
            # Include parent unit for attached units
            try:
                pu = getattr(m, "parent_unit", None)
                if pu is not None:
                    label = f"{label} ({getattr(pu, 'name', 'Unit')})"
            except Exception:
                pass
            # Add wounds info
            try:
                w = getattr(m, "wounds", None)
                bw = getattr(m, "_base_wounds", None)
                if w is not None and bw is not None:
                    label = f"{label}  [W {w}/{bw}]"
            except Exception:
                pass
            if self.show_wargear:
                self.draw_button(screen, btn, "", color=BUTTON_BG)
                rect = self.buttons[btn]
                label_surface = self.font_small.render(label, True, TEXT_PRIMARY)
                screen.blit(label_surface, (rect.x + 12, rect.y + 8))
                try:
                    wargear = list(getattr(m, "wargear", []) or [])
                except Exception:
                    wargear = []
                if wargear:
                    counts = {}
                    for wg in wargear:
                        try:
                            name = str(getattr(wg, "name", "") or "").strip()
                        except Exception:
                            name = ""
                        if not name:
                            continue
                        counts[name] = counts.get(name, 0) + 1
                    parts = []
                    for name, count in counts.items():
                        if count > 1:
                            parts.append(f"{name} x{count}")
                        else:
                            parts.append(name)
                    wargear_text = "Wargear: " + ", ".join(parts) if parts else ""
                    if wargear_text:
                        self.draw_text_wrapped(
                            screen,
                            wargear_text,
                            rect.x + 12,
                            rect.y + 26,
                            rect.width - 24,
                            self.font_tiny,
                            TEXT_SECONDARY,
                            line_height=14,
                        )
            else:
                self.draw_button(screen, btn, label, color=BUTTON_BG)
            pygame.draw.rect(screen, PANEL_BORDER, self.buttons[btn], 1)
