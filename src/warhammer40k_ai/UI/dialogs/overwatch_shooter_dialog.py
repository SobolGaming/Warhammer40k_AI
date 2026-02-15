import pygame
from typing import List, Optional, Callable, Any
from types import SimpleNamespace

from .base_dialog import BaseDialog, BUTTON_SELECTED


class OverwatchShooterDialog(BaseDialog):
    """Dialog to select which friendly unit will fire Overwatch."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=560, height=420, draggable=True)
        self.candidates: List[Any] = []
        self.selected_index: Optional[int] = None
        self.on_confirm: Optional[Callable[[Any], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.enemy_unit: Any = None
        self._title: Optional[str] = None
        self._subtitle: Optional[str] = None
        self.list_rect = None
        self.decision_request = None
        self._option_entries: List[Any] = []

    def show(
        self,
        candidates: List[Any],
        enemy_unit: Any,
        on_confirm: Callable[[str], None],
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        *,
        decision_request=None,
    ):
        self.decision_request = decision_request
        self.candidates, self._option_entries = self._build_candidates(candidates)
        self.enemy_unit = enemy_unit
        self.selected_index = 0 if self.candidates else None
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._title = title
        self._subtitle = subtitle
        if not self.candidates:
            self.buttons.clear()
            self.button_states.clear()
            self.visible = False
            if callable(on_cancel):
                on_cancel()
            return False
        self._create_buttons()
        super().show()
        return True

    def hide(self):
        super().hide()
        self.candidates = []
        self.selected_index = None
        self.on_confirm = None
        self.on_cancel = None
        self.enemy_unit = None
        self._title = None
        self._subtitle = None
        self.buttons.clear()
        self.button_states.clear()
        self.decision_request = None
        self._option_entries = []

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()
        self.add_button('select', self.width - 220, self.height - 50, 120, 35)
        self.add_button('cancel', self.width - 95, self.height - 50, 90, 35)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == 'select':
            if self.selected_index is not None and 0 <= self.selected_index < len(self.candidates):
                opt = self._option_entries[self.selected_index] if self.selected_index < len(self._option_entries) else None
                if callable(self.on_confirm) and opt is not None:
                    self.on_confirm(opt.option_id)
            return True
        if button_name in ('cancel', 'close'):
            if callable(self.on_cancel):
                self.on_cancel()
            self.hide()
            return True
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        enemy_name = getattr(self.enemy_unit, 'name', 'Enemy unit') if self.enemy_unit else 'Enemy unit'
        title = self._title or "Select Overwatch Shooter"
        subtitle = self._subtitle or f"Choose a unit to fire at {enemy_name}"
        self.draw_title_bar(screen, title, subtitle)
        self._update_buttons()

        # List area
        list_x = self.x + 16
        list_y = self.y + 64
        list_w = self.width - 32
        list_h = self.height - 120
        self.list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        pygame.draw.rect(screen, (50, 50, 55), self.list_rect)
        pygame.draw.rect(screen, (90, 90, 100), self.list_rect, 1)

        # Render candidate units
        line_h = 28
        max_lines = list_h // line_h
        visible = self.candidates[:max_lines]
        for i, unit in enumerate(visible):
            y = list_y + i * line_h
            is_sel = (self.selected_index == i)
            row = pygame.Rect(list_x + 2, y + 2, list_w - 4, line_h - 4)
            pygame.draw.rect(screen, BUTTON_SELECTED if is_sel else (60, 60, 67), row)
            pygame.draw.rect(screen, (63, 63, 70), row, 1)
            label = ""
            try:
                if self._option_entries and i < len(self._option_entries):
                    label = str(getattr(self._option_entries[i], "label", "") or "")
            except Exception:
                label = ""
            if not label:
                try:
                    label = getattr(unit, 'name', str(unit))
                except Exception:
                    label = str(unit)
            text = f"{label}"
            surf = self.font_small.render(text, True, (255, 255, 255))
            screen.blit(surf, (row.x + 8, row.y + 4))

        # Buttons
        self.draw_button(screen, 'select', 'Select')
        self.draw_button(screen, 'cancel', 'Cancel')

    def _handle_dialog_click(self, mouse_pos) -> bool:
        if self.list_rect and self.list_rect.collidepoint(mouse_pos):
            local_y = mouse_pos[1] - self.list_rect.y
            line_h = 28
            idx = local_y // line_h
            if 0 <= idx < len(self.candidates):
                self.selected_index = int(idx)
                return True
        return False

    def _build_candidates(self, candidates: List[Any]):
        if self.decision_request is None:
            return list(candidates or []), []
        try:
            from ...utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None
        options = list(getattr(self.decision_request, "options", []) or [])
        if not options:
            return list(candidates or []), []
        entries: List[Any] = []
        mapped: List[Any] = []
        unit_by_id = {}
        if get_entity_id is not None:
            for unit in list(candidates or []):
                if unit is None:
                    continue
                try:
                    unit_id = get_entity_id(unit)
                except (AttributeError, TypeError, ValueError):
                    unit_id = None
                if unit_id:
                    unit_by_id[str(unit_id)] = unit
        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            unit_id = str(payload.get("unit_id", payload.get("unit", "")) or "")
            unit = unit_by_id.get(unit_id) if unit_id else None
            if unit is None:
                label = str(getattr(opt, "label", "") or payload.get("label") or "Option")
                unit = SimpleNamespace(name=label)
            mapped.append(unit)
            entries.append(opt)
        return mapped, entries

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if callable(self.on_cancel):
                    self.on_cancel()
                self.hide()
                return True
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.selected_index is not None and self.candidates:
                    self.selected_index = max(0, self.selected_index - 1)
                    return True
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.selected_index is not None and self.candidates:
                    self.selected_index = min(len(self.candidates) - 1, self.selected_index + 1)
                    return True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.selected_index is not None and self.candidates:
                    opt = self._option_entries[self.selected_index] if self.selected_index < len(self._option_entries) else None
                    if callable(self.on_confirm) and opt is not None:
                        self.on_confirm(opt.option_id)
                    return True
        return False
