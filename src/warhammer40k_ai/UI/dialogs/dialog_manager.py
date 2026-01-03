from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List

import pygame


@dataclass
class _StackEntry:
    dialog: Any
    modal: bool = True


class DialogManager:
    """
    Centralized modal dialog stack.

    - Drawing: bottom -> top (stack order)
    - Events: topmost active dialog gets first chance; if modal, blocks underlying UI
    - Auto-prune: dialogs that are no longer active are removed from the stack

    A dialog is considered "active" if:
    - dialog.visible is True
    - OR it exposes is_targeting_mode=True (e.g. targeting overlays)
    """

    def __init__(self, game_view: Any):
        self.game_view = game_view
        self._stack: List[_StackEntry] = []
        self._was_active: dict[int, bool] = {}

    def _discover_dialogs(self) -> List[Any]:
        """
        Best-effort discovery of dialogs that may exist on game_view / ui_interface.

        This is intentionally centralized so adding a new dialog only requires:
        - assign it onto game_view (or game_view.ui_interface)
        - (optionally) add its attribute name here for better priority ordering
        """
        gv = self.game_view
        ui = getattr(gv, "ui_interface", None)

        def _get(obj, name: str):
            try:
                return getattr(obj, name)
            except Exception:
                return None

        # Lower priority -> higher priority (later becomes topmost if newly activated)
        discovered: List[Any] = []

        # UI-interface dialogs
        if ui is not None:
            discovered.extend([
                _get(ui, "scout_choice_dialog"),
                _get(ui, "fight_unit_selection_dialog"),
            ])

        # GameView dialogs / overlays
        discovered.extend([
            _get(gv, "yes_no_dialog"),
            _get(gv, "blessings_of_khorne_dialog"),
            _get(gv, "secondary_discard_dialog"),
            _get(gv, "overwatch_shooter_dialog"),
            _get(gv, "hazard_objective_select_dialog"),
            _get(gv, "battlefield_point_pick_dialog"),
            _get(gv, "movement_choice_dialog"),
            _get(gv, "individual_model_movement_dialog"),
            _get(gv, "coherency_violation_dialog"),
            _get(gv, "weapon_choice_dialog"),
            _get(gv, "shooting_declaration_dialog"),
            _get(gv, "charge_declaration_dialog"),
            _get(gv, "melee_weapon_declaration_dialog"),
            _get(gv, "fight_target_selection_dialog"),
            _get(gv, "target_model_selection_dialog"),
            _get(gv, "firing_deck_dialog"),
            _get(gv, "transport_embark_dialog"),
            _get(gv, "transport_disembark_dialog"),
            _get(gv, "transport_assignment_dialog"),
            _get(gv, "reserves_allocation_dialog"),
            _get(gv, "precision_allocation_dialog"),
            _get(gv, "damage_allocation_dialog"),
            _get(gv, "mission_selection_dialog"),
            _get(gv, "leader_attachment_dialog"),
        ])

        return [d for d in discovered if d is not None]

    def _sync(self) -> None:
        """Ensure newly-activated discovered dialogs are placed on top of the stack."""
        discovered = self._discover_dialogs()
        # Mark inactive ones in was_active dict
        active_now_ids = set()
        for d in discovered:
            if self.is_active(d):
                active_now_ids.add(id(d))

        for d in discovered:
            did = id(d)
            active = self.is_active(d)
            prev = bool(self._was_active.get(did, False))
            self._was_active[did] = active
            if active and (not prev):
                # Newly active: bring to top
                self.open(d, modal=True)

        # Drop stale entries
        self._prune()

    def is_active(self, dialog: Any) -> bool:
        try:
            if bool(getattr(dialog, "visible", False)):
                return True
        except Exception:
            pass
        try:
            if bool(getattr(dialog, "is_targeting_mode", False)):
                return True
        except Exception:
            pass
        return False

    def _prune(self) -> None:
        # Remove inactive dialogs from the stack (from top down).
        pruned: List[_StackEntry] = []
        for entry in self._stack:
            if self.is_active(entry.dialog):
                pruned.append(entry)
        self._stack = pruned

    def open(self, dialog: Any, modal: bool = True) -> None:
        """Push a dialog onto the stack as topmost. Caller is responsible for calling dialog.show()."""
        if dialog is None:
            return
        # Ensure it's topmost if already present
        self._stack = [e for e in self._stack if e.dialog is not dialog]
        self._stack.append(_StackEntry(dialog=dialog, modal=modal))

    def close(self, dialog: Optional[Any] = None) -> None:
        """Close a dialog (hide + remove). If dialog is None, closes the topmost."""
        if not self._stack:
            return
        if dialog is None:
            entry = self._stack.pop()
            d = entry.dialog
        else:
            d = dialog
            self._stack = [e for e in self._stack if e.dialog is not dialog]
        try:
            if hasattr(d, "hide"):
                d.hide()
            elif hasattr(d, "visible"):
                setattr(d, "visible", False)
        except Exception:
            pass

    def top(self) -> Optional[Any]:
        self._sync()
        return self._stack[-1].dialog if self._stack else None

    def handle_event(self, event: Any) -> bool:
        """Route event to topmost active dialog. Returns True if consumed."""
        self._sync()
        if not self._stack:
            return False

        # Only the topmost dialog gets events (modal stack concept)
        entry = self._stack[-1]
        dialog = entry.dialog
        try:
            handled = bool(dialog.handle_event(event))
        except Exception:
            handled = False

        # If the dialog became inactive, prune it.
        self._sync()

        # If the dialog intentionally returned False and requests passthrough, allow the underlying
        # phase handler to process the event (e.g. battlefield clicks for per-model deployment).
        if not handled and self.is_active(dialog):
            try:
                if hasattr(dialog, "should_passthrough_event") and callable(getattr(dialog, "should_passthrough_event")):
                    if bool(dialog.should_passthrough_event(event)):
                        return False
            except Exception:
                pass

        # If modal, always consume the event while active (even if not "handled"),
        # to prevent clicks/keys from leaking into the game.
        if entry.modal and self.is_active(dialog):
            # Allow MOUSEMOTION to pass through so phase handlers can keep updating hover/path previews
            # while a modal is open. Clicks/keys/wheel remain blocked.
            try:
                if getattr(event, "type", None) == pygame.MOUSEMOTION:
                    return handled
            except Exception:
                pass
            return True
        return handled

    def draw(self, screen: Any) -> None:
        """Draw all active dialogs in stack order."""
        self._sync()
        for entry in self._stack:
            d = entry.dialog
            try:
                if self.is_active(d) and hasattr(d, "draw"):
                    d.draw(screen)
            except Exception:
                continue


