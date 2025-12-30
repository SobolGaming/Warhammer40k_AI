import pygame
from typing import Optional, Callable, Any

from .base_dialog import BaseDialog


class SideBySideModal:
    """
    A lightweight modal container that displays two dialogs side-by-side (left + right)
    and routes events to whichever dialog the user interacts with.

    Motivation: Declare Battle Formations requires both players to make choices concurrently.
    The existing DialogManager is stack-based and only routes input to a single top dialog,
    so we wrap two dialogs into one modal "surface".
    """

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        left: BaseDialog,
        right: BaseDialog,
        *,
        on_both_done: Optional[Callable[[], None]] = None,
    ):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.left = left
        self.right = right
        self.on_both_done = on_both_done
        self.visible = False

        # Optional helper: set by callers when a side completes
        self.left_done = False
        self.right_done = False

        # Draw a dark overlay behind dialogs when modal is active
        self._overlay = pygame.Surface((screen_width, screen_height))
        self._overlay.set_alpha(96)
        self._overlay.fill((0, 0, 0))

    def show(self) -> None:
        self.visible = True
        try:
            self.left.visible = True
        except Exception:
            pass
        try:
            self.right.visible = True
        except Exception:
            pass

    def hide(self) -> None:
        self.visible = False
        try:
            self.left.hide()
        except Exception:
            try:
                self.left.visible = False
            except Exception:
                pass
        try:
            self.right.hide()
        except Exception:
            try:
                self.right.visible = False
            except Exception:
                pass

    def _contains(self, dlg: BaseDialog, pos) -> bool:
        try:
            x, y = pos
        except Exception:
            return False
        try:
            rect = pygame.Rect(dlg.x, dlg.y, dlg.width, dlg.height)
            return rect.collidepoint((x, y))
        except Exception:
            return False

    def handle_event(self, event: Any) -> bool:
        if not self.visible:
            return False

        # ESC closes the whole modal (and both dialogs)
        try:
            if getattr(event, "type", None) == pygame.KEYDOWN and getattr(event, "key", None) == pygame.K_ESCAPE:
                self.hide()
                return True
        except Exception:
            pass

        # Mouse events: route based on cursor position.
        pos = None
        try:
            if hasattr(event, "pos"):
                pos = event.pos
        except Exception:
            pos = None

        # Prefer the dialog under the cursor; if none, still forward to both (so they can handle
        # wheel scrolling / hover) and then consume.
        if pos is not None:
            if self._contains(self.left, pos):
                try:
                    return bool(self.left.handle_event(event))
                except Exception:
                    return True
            if self._contains(self.right, pos):
                try:
                    return bool(self.right.handle_event(event))
                except Exception:
                    return True

        # Keyboard events: forward to both (best effort)
        handled = False
        try:
            handled = bool(self.left.handle_event(event)) or handled
        except Exception:
            pass
        try:
            handled = bool(self.right.handle_event(event)) or handled
        except Exception:
            pass

        return bool(handled) or True

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        try:
            screen.blit(self._overlay, (0, 0))
        except Exception:
            pass
        try:
            if getattr(self.left, "visible", False) and hasattr(self.left, "draw"):
                self.left.draw(screen)
        except Exception:
            pass
        try:
            if getattr(self.right, "visible", False) and hasattr(self.right, "draw"):
                self.right.draw(screen)
        except Exception:
            pass


