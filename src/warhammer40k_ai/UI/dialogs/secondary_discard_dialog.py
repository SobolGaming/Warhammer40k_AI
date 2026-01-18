import pygame
from typing import List, Optional, Callable, Any

from .base_dialog import BaseDialog, BUTTON_SELECTED


class SecondaryDiscardDialog(BaseDialog):
    """Dialog to choose which active Secondary Mission card to discard."""

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=520, height=360, draggable=True)
        self.cards: List[Any] = []
        self.selected_index: Optional[int] = None
        self.on_confirm: Optional[Callable[[Any], None]] = None
        self.list_rect = None

    def show(self, cards: List[Any], on_confirm: Callable[[Any], None]):
        super().show()
        self.cards = list(cards)
        self.selected_index = 0 if self.cards else None
        self.on_confirm = on_confirm
        self._create_buttons()

    def hide(self):
        super().hide()
        self.cards = []
        self.selected_index = None
        self.on_confirm = None
        self.buttons.clear()
        self.button_states.clear()

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()
        self.add_button('discard', self.width - 220, self.height - 50, 120, 35)
        self.add_button('cancel', self.width - 95, self.height - 50, 90, 35)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == 'discard':
            if self.selected_index is not None and 0 <= self.selected_index < len(self.cards):
                card = self.cards[self.selected_index]
                if callable(self.on_confirm):
                    self.on_confirm(card)
            return True
        if button_name in ('cancel', 'close'):
            self.hide()
            return True
        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        title = "Discard a Secondary"
        subtitle = "Choose one active Secondary to discard"
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

        # Render cards
        line_h = 28
        max_lines = list_h // line_h
        visible = self.cards[:max_lines]
        for i, card in enumerate(visible):
            y = list_y + i * line_h
            is_sel = (self.selected_index == i)
            row = pygame.Rect(list_x + 2, y + 2, list_w - 4, line_h - 4)
            pygame.draw.rect(screen, BUTTON_SELECTED if is_sel else (60, 60, 67), row)
            pygame.draw.rect(screen, (63, 63, 70), row, 1)
            try:
                name = getattr(card, 'name', str(card))
                desc = getattr(card, 'description', '')
            except Exception:
                name, desc = str(card), ''
            text = f"{name}"
            surf = self.font_small.render(text, True, (255, 255, 255))
            screen.blit(surf, (row.x + 8, row.y + 4))

        # Buttons
        self.draw_button(screen, 'discard', 'Discard')
        self.draw_button(screen, 'cancel', 'Cancel')

    def _handle_dialog_click(self, mouse_pos) -> bool:
        if self.list_rect and self.list_rect.collidepoint(mouse_pos):
            local_y = mouse_pos[1] - self.list_rect.y
            line_h = 28
            idx = local_y // line_h
            if 0 <= idx < len(self.cards):
                self.selected_index = int(idx)
                return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.selected_index is not None and self.cards:
                    self.selected_index = max(0, self.selected_index - 1)
                    return True
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.selected_index is not None and self.cards:
                    self.selected_index = min(len(self.cards) - 1, self.selected_index + 1)
                    return True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.selected_index is not None and self.cards:
                    card = self.cards[self.selected_index]
                    if callable(self.on_confirm):
                        self.on_confirm(card)
                    return True
        return False
