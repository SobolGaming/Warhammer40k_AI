from __future__ import annotations

from typing import Any, Callable, Optional

import pygame


class MissionSelectionModal:
    """
    Adapter that makes MissionSelectionDialog behave like a callback-based modal.

    MissionSelectionDialog is an older/special dialog that returns dicts from handle_event();
    this adapter converts those to callbacks and fits the DialogManager contract.
    """

    def __init__(self, inner_dialog: Any):
        self._inner = inner_dialog
        self.visible = False
        self._on_confirm: Optional[Callable[[dict], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None
        self._decision_request = None

    def show(self, *, on_confirm: Callable[[dict], None], on_cancel: Optional[Callable[[], None]] = None, decision_request=None) -> None:
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._decision_request = decision_request
        self.visible = True
        try:
            if hasattr(self._inner, "show"):
                self._inner.show(decision_request=decision_request)
            else:
                self._inner.visible = True
        except Exception:
            pass

    def hide(self) -> None:
        self.visible = False
        try:
            self._inner.visible = False
        except Exception:
            pass
        self._on_confirm = None
        self._on_cancel = None
        self._decision_request = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        try:
            result = self._inner.handle_event(event)
        except Exception:
            result = None

        if isinstance(result, dict):
            action = result.get("action")
            if action == "confirm":
                if self._on_confirm:
                    self._on_confirm(result)
                self.hide()
                return True
            if action == "cancel":
                if self._on_cancel:
                    self._on_cancel()
                self.hide()
                return True

        # While visible, treat as modal (DialogManager will consume input anyway)
        return True

    def draw(self, screen) -> None:
        if not self.visible:
            return
        try:
            self._inner.draw(screen)
        except Exception:
            pass

