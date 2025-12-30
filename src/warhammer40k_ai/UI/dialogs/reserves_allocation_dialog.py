import pygame
from typing import List, Optional, Callable, Dict, Tuple

from .base_dialog import (
    BaseDialog,
    PANEL_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_WARNING,
    BUTTON_BG,
    BUTTON_SELECTED,
)


class ReservesAllocationDialog(BaseDialog):
    """
    Declare Battle Formations dialog: allocate reserve status for a single army.

    Rules enforced (Chapter Approved defaults, via Army.get_reserve_limits()):
    - Total reserves (Reserves + Strategic Reserves): <= 50% points AND <= 50% unit-count (post-attachment/embark groups)
    - Strategic Reserves: <= 25% battle size points
    - Standard Reserves require Deep Strike (best-effort via unit.has_deep_strike()).

    This dialog operates on "deployment groups" (roots):
    - attached leaders are not selectable separately
    - embarked units are not selectable separately
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=900, height=560, draggable=True, center=True)
        self.title = "Allocate Reserves (Declare Battle Formations)"

        self.army = None
        self.root_units: List = []
        self._display_names: Dict[str, str] = {}

        # state per root-id: 'deploy' | 'reserves' | 'strategic_reserves'
        self.decisions: Dict[str, str] = {}

        self.selected_index: int = 0
        self.scroll_offset: int = 0
        self.max_scroll: int = 0

        self.on_confirm: Optional[Callable[[Dict[str, str]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self._message: str = ""
        self._message_color = TEXT_SECONDARY

    def show(self, army, *, on_confirm: Callable[[Dict[str, str]], None], on_cancel: Optional[Callable[[], None]] = None) -> None:
        self.army = army
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.scroll_offset = 0
        self.selected_index = 0
        self._message = ""
        self._message_color = TEXT_SECONDARY

        self.root_units = self._compute_roots()
        self._recompute_display_names()
        self.decisions = {self._uid(u): "deploy" for u in self.root_units}

        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.army = None
        self.root_units = []
        self._display_names = {}
        self.decisions = {}
        self.selected_index = 0
        self.scroll_offset = 0
        self.max_scroll = 0
        self.on_confirm = None
        self.on_cancel = None
        self._message = ""
        self._message_color = TEXT_SECONDARY

    # -------------------------------
    # Helpers
    # -------------------------------
    def _uid(self, unit) -> str:
        try:
            return str(getattr(unit, "_id", None) or id(unit))
        except Exception:
            return str(id(unit))

    def _compute_roots(self) -> List:
        if self.army is None:
            return []
        units = list(getattr(self.army, "units", []) or [])
        roots = []
        for u in units:
            if u is None:
                continue
            try:
                if bool(getattr(u, "is_attached_leader", False)):
                    continue
            except Exception:
                pass
            try:
                if bool(getattr(u, "is_embarked", False)) or getattr(u, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            roots.append(u)
        roots.sort(key=lambda u: str(getattr(u, "name", "")))
        return roots

    def _recompute_display_names(self) -> None:
        self._display_names = {}
        # disambiguate duplicate names within this army
        counts: Dict[str, int] = {}
        for u in self.root_units:
            nm = str(getattr(u, "name", "Unit"))
            counts[nm] = counts.get(nm, 0) + 1
        running: Dict[str, int] = {}
        for u in self.root_units:
            nm = str(getattr(u, "name", "Unit"))
            uid = self._uid(u)
            if counts.get(nm, 0) > 1:
                running[nm] = running.get(nm, 0) + 1
                self._display_names[uid] = f"{nm} {running[nm]}"
            else:
                self._display_names[uid] = nm

    def _display_name(self, unit) -> str:
        uid = self._uid(unit)
        return self._display_names.get(uid, str(getattr(unit, "name", "Unit")))

    def _group_points(self, root) -> int:
        # Mirror Army._reserve_group_points (but keep dialog independent)
        total = 0
        try:
            total += int(root.get_unit_cost())
        except Exception:
            pass
        try:
            for l in list(getattr(root, "attached_leaders", []) or []):
                try:
                    total += int(l.get_unit_cost())
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if bool(getattr(root, "is_transport", False)):
                for p in list(getattr(root, "transport_passengers", []) or []):
                    try:
                        total += int(p.get_unit_cost())
                    except Exception:
                        pass
                    try:
                        for l in list(getattr(p, "attached_leaders", []) or []):
                            try:
                                total += int(l.get_unit_cost())
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass
        return int(total)

    def _current_totals_with_override(self, *, override: Optional[Tuple[int, str]] = None) -> Tuple[int, int, int]:
        """
        Returns (reserve_units, reserve_points, strategic_points) for the current decisions.
        If override is provided, uses that (index, decision) instead of current.
        """
        reserve_units = 0
        reserve_points = 0
        strategic_points = 0
        for i, u in enumerate(self.root_units):
            uid = self._uid(u)
            decision = self.decisions.get(uid, "deploy")
            if override and override[0] == i:
                decision = override[1]
            if decision in ("reserves", "strategic_reserves"):
                reserve_units += 1
                pts = self._group_points(u)
                reserve_points += pts
                if decision == "strategic_reserves":
                    strategic_points += pts
        return reserve_units, reserve_points, strategic_points

    def _can_set_decision(self, idx: int, decision: str) -> Tuple[bool, str]:
        if self.army is None:
            return False, "No army"
        if not (0 <= idx < len(self.root_units)):
            return False, "Invalid selection"

        unit = self.root_units[idx]

        # Fortifications cannot be placed into Strategic Reserves.
        if decision == "strategic_reserves":
            try:
                if bool(getattr(unit, "is_fortification", False)):
                    return False, "FORTIFICATIONS cannot be placed in Strategic Reserves"
            except Exception:
                pass

        # Standard Reserves requires Deep Strike (best-effort)
        if decision == "reserves":
            try:
                if not bool(unit.has_deep_strike()):
                    return False, "Requires Deep Strike"
            except Exception:
                return False, "Requires Deep Strike"

        limits = self.army.get_reserve_limits()
        reserve_units, reserve_points, strategic_points = self._current_totals_with_override(override=(idx, decision))

        if reserve_units > limits["max_units"]:
            return False, f"Exceeds reserves unit cap ({reserve_units}/{limits['max_units']})"
        if reserve_points > limits["max_points"]:
            return False, f"Exceeds reserves points cap ({reserve_points}/{limits['max_points']})"
        if strategic_points > limits["max_strategic_points"]:
            return False, f"Exceeds strategic points cap ({strategic_points}/{limits['max_strategic_points']})"

        return True, ""

    # -------------------------------
    # UI plumbing
    # -------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if super().handle_event(event):
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll_offset = max(0, self.scroll_offset - 24)
                return True
            if event.button == 5:
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 24)
                return True
        return False

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name == "done":
            # Validate before confirming
            if self.army is not None:
                status = self.army.validate_reserves_decisions(self.decisions)
                if not status.get("valid", False):
                    errs = status.get("errors", []) or []
                    self._message = errs[0] if errs else "Invalid reserves allocation"
                    self._message_color = TEXT_WARNING
                    return True
            if self.on_confirm:
                self.on_confirm(dict(self.decisions))
            self.hide()
            return True

        if button_name.startswith("unit_"):
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            self.selected_index = max(0, min(idx, len(self.root_units) - 1))
            return True

        if button_name in ("clear_reserves", "set_reserves", "set_strategic"):
            idx = self.selected_index
            # "Deploy" is implicit; clearing reserves means "not in reserves".
            target = "deploy" if button_name == "clear_reserves" else ("reserves" if button_name == "set_reserves" else "strategic_reserves")
            ok, reason = self._can_set_decision(idx, target)
            if not ok:
                self._message = reason
                self._message_color = TEXT_WARNING
                return True
            u = self.root_units[idx]
            self.decisions[self._uid(u)] = target
            self._message = ""
            self._message_color = TEXT_SECONDARY
            return True

        return False

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()

        pad = 16
        list_top = self.title_bar_height + 70
        list_bottom = self.height - 70
        row_h = 54
        row_gap = 10

        left_w = 520
        right_w = self.width - left_w - pad * 3
        right_x = pad * 2 + left_w

        # List buttons (left)
        for i, _u in enumerate(self.root_units):
            rel_y = list_top + i * (row_h + row_gap) - self.scroll_offset
            if rel_y + row_h < list_top or rel_y > list_bottom:
                continue
            self.add_button(f"unit_{i}", pad, rel_y, left_w, row_h, enabled=True)

        total_left = len(self.root_units) * (row_h + row_gap)
        list_h = list_bottom - list_top
        self.max_scroll = max(0, total_left - list_h)

        # Right-side action buttons
        btn_w = right_w
        btn_h = 44
        self.add_button("set_reserves", right_x, list_top, btn_w, btn_h, enabled=True)
        self.add_button("set_strategic", right_x, list_top + 54, btn_w, btn_h, enabled=True)
        self.add_button("clear_reserves", right_x, list_top + 108, btn_w, btn_h, enabled=True)

        # Bottom
        self.add_button("done", self.width - 260, self.height - 55, 110, 38, enabled=True)
        self.add_button("cancel", self.width - 140, self.height - 55, 110, 38, enabled=True)

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)

        # Subtitle with current totals
        pname = ""
        try:
            pname = getattr(getattr(self.army, "player", None), "name", "")
        except Exception:
            pname = ""
        limits = self.army.get_reserve_limits() if self.army is not None else {}
        reserve_units, reserve_points, strategic_points = self._current_totals_with_override()
        subtitle = (
            f"{pname} | Reserves: {reserve_units}/{limits.get('max_units', 0)} units, "
            f"{reserve_points}/{limits.get('max_points', 0)} pts | "
            f"Strategic: {strategic_points}/{limits.get('max_strategic_points', 0)} pts"
        )
        self.draw_title_bar(screen, self.title, subtitle=subtitle)

        pad = 16
        left_w = 520
        right_x = self.x + pad * 2 + left_w
        list_top = self.y + self.title_bar_height + 70

        # Instructions
        inst = "Select a group on the left, then set it to Reserves (Deep Strike) or Strategic Reserves. Unselected = not in reserves."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + pad, self.y + self.title_bar_height + 10))

        # Update buttons per scroll
        self._create_buttons()
        self._update_buttons()

        # Draw list
        for i, u in enumerate(self.root_units):
            btn_name = f"unit_{i}"
            if btn_name not in self.buttons:
                continue
            rect = self.buttons[btn_name]
            if btn_name in self.button_states:
                self.button_states[btn_name]["state"] = "selected" if i == self.selected_index else "normal"
            self.draw_button(screen, btn_name, self._display_name(u), color=BUTTON_BG)

            # Secondary: points + current choice
            pts = self._group_points(u)
            uid = self._uid(u)
            choice = self.decisions.get(uid, "deploy")
            choice_label = "Not in Reserves" if choice == "deploy" else ("Reserves" if choice == "reserves" else "Strategic")
            info = f"{pts} pts | {choice_label}"
            info_surface = self.font_tiny.render(info, True, TEXT_SECONDARY)
            screen.blit(info_surface, (rect.x + 12, rect.y + rect.height - 18))

            if i == self.selected_index:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        # Right-side buttons: enable/disable based on selection + caps
        def _set_enabled(btn: str, enabled: bool) -> None:
            if btn in self.button_states:
                self.button_states[btn]["enabled"] = bool(enabled)

        idx = self.selected_index
        ok_res, _ = self._can_set_decision(idx, "reserves")
        ok_str, _ = self._can_set_decision(idx, "strategic_reserves")
        _set_enabled("clear_reserves", True)
        _set_enabled("set_reserves", ok_res)
        _set_enabled("set_strategic", ok_str)

        # Draw right-side action buttons
        self.draw_button(screen, "set_reserves", "Set: Reserves (Deep Strike)")
        self.draw_button(screen, "set_strategic", "Set: Strategic Reserves")
        self.draw_button(screen, "clear_reserves", "Remove from Reserves")

        # Message
        if self._message:
            msg = self.font_tiny.render(self._message, True, self._message_color)
            screen.blit(msg, (self.x + pad, self.y + self.height - 58))

        # Bottom
        self.draw_button(screen, "done", "Done")
        self.draw_button(screen, "cancel", "Cancel")


