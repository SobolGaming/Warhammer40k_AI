import pygame
from typing import List, Optional, Dict, Any, Callable

from .base_dialog import BaseDialog, BUTTON_SELECTED


class StratagemDialog(BaseDialog):
    """Interactive Stratagem selection dialog.

    Shows pending reactions and phase-available stratagems for a player.
    Allows selecting one and attempting to use it via the player's StratagemManager.
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=520, height=460, draggable=True)
        self.player = None
        self.game = None
        self.manager = None
        self.items: List[Dict[str, Any]] = []
        self.selected_index: Optional[int] = None
        self.on_closed: Optional[Callable[[], None]] = None

        # UI layout
        self.list_rect = None

    def show(self, player, game, on_closed: Optional[Callable[[], None]] = None):
        super().show(callback=None)
        self.player = player
        self.game = game
        self.on_closed = on_closed
        self.manager = getattr(player, 'stratagems', None)
        self._rebuild_items()
        self.selected_index = 0 if self.items else None

    def hide(self):
        super().hide()
        if callable(self.on_closed):
            try:
                self.on_closed()
            except Exception:
                pass
        self.player = None
        self.game = None
        self.manager = None
        self.items = []
        self.selected_index = None
        self.on_closed = None

    def _rebuild_items(self) -> None:
        self.items = []
        if not self.manager:
            return
        # Pending reactions first
        try:
            pending = self.manager.get_pending_reactions() or []
        except Exception:
            pending = []
        for r in pending:
            name = r.get('stratagem', 'Stratagem')
            label = f"[Reaction] {name}"
            self.items.append({'type': 'reaction', 'name': name, 'context': r, 'label': label})
        # Phase-available generic stratagems
        try:
            avail = self.manager.list_available_for_current_phase() or []
        except Exception:
            avail = []
        for s in avail:
            try:
                name = getattr(s, 'name', 'Stratagem')
            except Exception:
                name = 'Stratagem'
            self.items.append({'type': 'available', 'name': name, 'context': {}, 'label': name})

    def _attempt_use_selected(self) -> None:
        if self.selected_index is None or not self.manager or self.selected_index >= len(self.items):
            return
        item = self.items[self.selected_index]
        name = item.get('name')
        context = dict(item.get('context', {}))
        # For reactions, include dequeue=True to drop it after success
        if item.get('type') == 'reaction':
            context['dequeue'] = True
        # Ensure phase_name for checks
        if 'phase_name' not in context:
            try:
                phase_name = getattr(self.manager, '_current_phase_name', None)
                if phase_name:
                    context['phase_name'] = phase_name
            except Exception:
                pass
        # If NEW ORDERS without a specified secondary, ask GameView to open selection dialog
        if name and str(name).strip().upper() == 'NEW ORDERS' and 'secondary_card' not in context:
            # Defer to GameView's dialog to collect the card, then re-invoke use
            gv = getattr(self.game, 'ui', None)
            # If the game stores a UI reference, use that; else, try to call via player.game
            try:
                from ..UI.game_ui import GameView  # type: ignore
            except Exception:
                GameView = None  # type: ignore
            # We expect the Game to be owned by a GameView in play mode; inject callback hook
            if hasattr(self, 'on_request_secondary_discard') and callable(self.on_request_secondary_discard):
                self.on_request_secondary_discard(self.player, self.game, lambda chosen: self._finalize_new_orders(chosen))
                return
            # Fallback: close and fail fast if wiring is missing
            print("❌ NEW ORDERS: UI hook for secondary selection not available")
            return

        ok = self.manager.use(name, **context)
        if ok:
            print(f"✅ Used stratagem: {name}")
            # Close after successful use; GameView will resume flow via on_closed callback
            self.hide()
        else:
            print(f"❌ Could not use stratagem: {name}")

    def _finalize_new_orders(self, selected_card) -> None:
        """Called after the user picks which Secondary to discard for NEW ORDERS."""
        if self.selected_index is None or not self.manager or self.selected_index >= len(self.items):
            return
        item = self.items[self.selected_index]
        name = item.get('name')
        context = dict(item.get('context', {}))
        context['secondary_card'] = selected_card
        # Ensure reaction dequeue if applicable
        if item.get('type') == 'reaction':
            context['dequeue'] = True
        if 'phase_name' not in context:
            phase_name = getattr(self.manager, '_current_phase_name', None)
            if phase_name:
                context['phase_name'] = phase_name
        ok = self.manager.use(name, **context)
        if ok:
            print(f"✅ Used stratagem: {name}")
            self.hide()
        else:
            print(f"❌ Could not use stratagem: {name}")

    # --- Event handling ---
    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == 'use':
            self._attempt_use_selected()
            return True
        if button_name in ('close', 'cancel'):
            self.hide()
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        # Support list selection via click inside dialog
        if self.list_rect and self.list_rect.collidepoint(mouse_pos):
            local_y = mouse_pos[1] - self.list_rect.y
            line_h = 24
            idx = local_y // line_h
            if 0 <= idx < len(self.items):
                self.selected_index = int(idx)
                return True
        return False

    def _handle_other_events(self, event: pygame.event.Event) -> bool:
        # Keyboard navigation and Enter to use
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.selected_index is not None and self.items:
                    self.selected_index = max(0, self.selected_index - 1)
                    return True
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.selected_index is not None and self.items:
                    self.selected_index = min(len(self.items) - 1, self.selected_index + 1)
                    return True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._attempt_use_selected()
                return True
        return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        # ESC closes
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.hide()
            return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.x = event.pos[0] - self.drag_offset_x
                self.y = event.pos[1] - self.drag_offset_y
                self.x = max(0, min(self.screen_width - self.width, self.x))
                self.y = max(0, min(self.screen_height - self.height, self.y))
                self._update_title_bar()
                self._update_buttons()
                return True
            return False

        return super().handle_event(event)

    # --- Drawing ---
    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        title = f"Stratagems - {getattr(self.player, 'name', 'Player')}"
        subtitle = "Choose a stratagem or Close"
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

        # Render items
        line_h = 24
        max_lines = list_h // line_h
        visible_items = self.items[:max_lines]
        for i, item in enumerate(visible_items):
            y = list_y + i * line_h
            is_sel = (self.selected_index == i)
            bg = BUTTON_SELECTED if is_sel else (60, 60, 67)
            row_rect = pygame.Rect(list_x + 2, y + 2, list_w - 4, line_h - 4)
            pygame.draw.rect(screen, bg, row_rect)
            pygame.draw.rect(screen, (63, 63, 70), row_rect, 1)
            try:
                font = pygame.font.SysFont('Arial', 14)
            except Exception:
                font = pygame.font.Font(None, 14)
            text_color = (255, 255, 255)
            label = item.get('label', item.get('name', 'Stratagem'))
            surface = font.render(label, True, text_color)
            screen.blit(surface, (row_rect.x + 8, row_rect.y + 3))

        # Buttons
        self.add_button('use', self.width - 190, self.height - 50, 90, 35)
        self.add_button('cancel', self.width - 95, self.height - 50, 90, 35)
        self.draw_button(screen, 'use', 'Use')
        self.draw_button(screen, 'cancel', 'Cancel')


