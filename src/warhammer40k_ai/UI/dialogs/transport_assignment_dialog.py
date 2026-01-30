import pygame
from typing import Dict, List, Optional, Callable, Set

from warhammer40k_ai.utility.entity_ids import get_entity_id

from .base_dialog import BaseDialog, BUTTON_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_SELECTED


class TransportAssignmentDialog(BaseDialog):
    """
    Setup-phase dialog for declaring which units start the battle embarked within Transports.

    10e: This is declared during DECLARE BATTLE FORMATIONS.
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=900, height=560, draggable=True, center=True)
        self.all_units: List = []
        self.transports: List = []
        self.selected_transport_index: int = 0
        self.decision_requests: Dict[str, object] = {}
        self._selected_option_ids: Dict[str, str] = {}

        # transport -> set(unit)
        self.assignments: Dict[object, Set[object]] = {}

        self.on_confirm: Optional[Callable[[Dict[str, str]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        # Scrolling per pane
        self.left_scroll = 0
        self.left_max_scroll = 0
        self.right_scroll = 0
        self.right_max_scroll = 0

    def show(
        self,
        all_units: List,
        *,
        unit_requests: Dict[str, object],
        on_confirm: Callable[[Dict[str, str]], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        self.all_units = list(all_units or [])
        # Transports that exist in armies (setup: not deployed yet)
        self.transports = [u for u in self.all_units if getattr(u, "is_transport", False)]
        self.transports.sort(key=lambda u: (getattr(getattr(u.get_parent_army(), "player", None), "name", ""), getattr(u, "name", "")))
        self.selected_transport_index = 0
        self.decision_requests = dict(unit_requests or {})

        # Seed assignments from current embarked state
        self.assignments = {}
        for t in self.transports:
            self.assignments[t] = set(getattr(t, "transport_passengers", []) or [])
        self._selected_option_ids = self._seed_selected_options()

        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.left_scroll = 0
        self.right_scroll = 0
        super().show()

    def hide(self) -> None:
        super().hide()
        self.all_units = []
        self.transports = []
        self.selected_transport_index = 0
        self.decision_requests = {}
        self._selected_option_ids = {}
        self.assignments = {}
        self.on_confirm = None
        self.on_cancel = None
        self.left_scroll = 0
        self.right_scroll = 0
        self.left_max_scroll = 0
        self.right_max_scroll = 0

    def _selected_transport(self):
        if not self.transports:
            return None
        idx = max(0, min(self.selected_transport_index, len(self.transports) - 1))
        return self.transports[idx]

    def _candidates_for_transport(self, transport_unit) -> List:
        if transport_unit is None:
            return []
        candidates = []
        for u in self.all_units:
            if u is None or u == transport_unit:
                continue
            # Don't show attached leader units separately
            if bool(getattr(u, "is_attached_leader", False)):
                continue
            # Don't show joined support artillery units separately
            if bool(getattr(u, "is_joined_support", False)):
                continue
            # Setup only: units that are not yet deployed. (Still allow if deployed = False.)
            # If you want to allow later "re-declare", we can relax this.
            if getattr(u, "deployed", False):
                continue
            # Already embarked elsewhere?
            if getattr(u, "embarked_in", None) is not None and getattr(u, "embarked_in", None) != transport_unit:
                continue
            # If assigned to a different transport in this dialog mapping
            for t, assigned in self.assignments.items():
                if t != transport_unit and u in assigned:
                    break
            else:
                pass
            # The above loop "break"s if found; detect it by checking membership again
            assigned_elsewhere = any((t != transport_unit and u in assigned) for t, assigned in self.assignments.items())
            if assigned_elsewhere:
                continue

            uid = get_entity_id(u)
            request = self.decision_requests.get(uid)
            options = list(getattr(request, "options", []) or []) if request is not None else []
            transport_id = get_entity_id(transport_unit)
            if not any(str(getattr(opt, "payload", {}).get("transport_id", "")) == transport_id for opt in options):
                continue

            candidates.append(u)

        candidates.sort(key=lambda u: getattr(u, "name", ""))
        return candidates

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()

        # Layout
        pad = 16
        left_w = 360
        right_w = self.width - left_w - pad * 3
        list_top = self.title_bar_height + 70
        list_bottom = self.height - 70
        list_h = list_bottom - list_top
        row_h = 54
        row_gap = 10

        # Left: transports
        for i, _t in enumerate(self.transports):
            rel_y = list_top + i * (row_h + row_gap) - self.left_scroll
            if rel_y + row_h < list_top or rel_y > list_bottom:
                continue
            self.add_button(f"transport_{i}", pad, rel_y, left_w, row_h, enabled=True)

        total_left = len(self.transports) * (row_h + row_gap)
        self.left_max_scroll = max(0, total_left - list_h)

        # Right: candidates for selected transport
        t = self._selected_transport()
        candidates = self._candidates_for_transport(t)
        start_x = pad * 2 + left_w
        for i, _u in enumerate(candidates):
            rel_y = list_top + i * (row_h + row_gap) - self.right_scroll
            if rel_y + row_h < list_top or rel_y > list_bottom:
                continue
            self.add_button(f"unit_{i}", start_x, rel_y, right_w, row_h, enabled=True)

        total_right = len(candidates) * (row_h + row_gap)
        self.right_max_scroll = max(0, total_right - list_h)

        # Actions
        self.add_button("confirm", self.width - 280, self.height - 55, 120, 38, enabled=True)
        self.add_button("cancel", self.width - 150, self.height - 55, 120, 38, enabled=True)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if super().handle_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Wheel scroll: choose pane based on cursor x
            if event.button in (4, 5):
                mx, my = event.pos
                inside = pygame.Rect(self.x, self.y, self.width, self.height).collidepoint(event.pos)
                if not inside:
                    return False
                rel_x = mx - self.x
                left_w = 360
                if rel_x <= 16 + left_w:
                    if event.button == 4:
                        self.left_scroll = max(0, self.left_scroll - 24)
                    else:
                        self.left_scroll = min(self.left_max_scroll, self.left_scroll + 24)
                else:
                    if event.button == 4:
                        self.right_scroll = max(0, self.right_scroll - 24)
                    else:
                        self.right_scroll = min(self.right_max_scroll, self.right_scroll + 24)
                return True

        return False

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name == "confirm":
            if self.on_confirm:
                self.on_confirm(dict(self._selected_option_ids))
            self.hide()
            return True

        if button_name.startswith("transport_"):
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            self.selected_transport_index = max(0, min(idx, len(self.transports) - 1))
            self.right_scroll = 0
            return True

        if button_name.startswith("unit_"):
            t = self._selected_transport()
            if t is None:
                return True
            candidates = self._candidates_for_transport(t)
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            if not (0 <= idx < len(candidates)):
                return True
            unit = candidates[idx]

            assigned = self.assignments.get(t, set())
            if unit in assigned:
                assigned.remove(unit)
                self.assignments[t] = assigned
                uid = get_entity_id(unit)
                self._selected_option_ids[uid] = self._option_for_transport(unit, None)
                return True

            # Capacity check when adding
            try:
                needed = unit.get_transport_slots_required()
            except Exception:
                needed = 0
            try:
                remaining = int(getattr(t, "transport_slots_remaining", 0))
            except Exception:
                remaining = 0
            if needed > remaining:
                return True

            assigned.add(unit)
            self.assignments[t] = assigned
            uid = get_entity_id(unit)
            self._selected_option_ids[uid] = self._option_for_transport(unit, t)
            return True

        return False

    def _option_for_transport(self, unit, transport_unit) -> str:
        uid = get_entity_id(unit)
        request = self.decision_requests.get(uid)
        options = list(getattr(request, "options", []) or []) if request is not None else []
        transport_id = get_entity_id(transport_unit) if transport_unit is not None else None
        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            if transport_id is None and payload.get("transport_id") is None:
                return opt.option_id
            if transport_id is not None and str(payload.get("transport_id", "")) == transport_id:
                return opt.option_id
        return ""

    def _seed_selected_options(self) -> Dict[str, str]:
        selected: Dict[str, str] = {}
        for unit in self.all_units:
            if unit is None or bool(getattr(unit, "is_transport", False)):
                continue
            uid = get_entity_id(unit)
            if uid not in self.decision_requests:
                continue
            current_transport = getattr(unit, "embarked_in", None)
            selected[uid] = self._option_for_transport(unit, current_transport)
        return selected

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, "Transport Assignments", subtitle="Declare which units start embarked (Declare Battle Formations)")

        # Instructions
        inst = "Select a Transport on the left, then select units on the right to start embarked (capacity-aware)."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 16, self.y + self.title_bar_height + 10))

        # Refresh buttons per scroll/selection
        self._create_buttons()
        self._update_buttons()

        # Layout constants
        pad = 16
        left_w = 360
        start_x = self.x + pad
        start_y = self.y + self.title_bar_height + 70

        # Left pane label
        ltitle = self.font_small.render("Transports", True, TEXT_PRIMARY)
        screen.blit(ltitle, (self.x + pad, self.y + self.title_bar_height + 42))

        # Right pane label
        rtitle = self.font_small.render("Eligible Units", True, TEXT_PRIMARY)
        screen.blit(rtitle, (self.x + pad * 2 + left_w, self.y + self.title_bar_height + 42))

        # Draw transport rows
        for i, t in enumerate(self.transports):
            btn_name = f"transport_{i}"
            if btn_name not in self.buttons:
                continue
            rect = self.buttons[btn_name]
            if btn_name in self.button_states:
                self.button_states[btn_name]['state'] = 'selected' if i == self.selected_transport_index else 'normal'

            pname = getattr(getattr(t.get_parent_army(), "player", None), "name", "")
            label = f"{pname}: {getattr(t, 'name', 'Transport')}" if pname else getattr(t, 'name', 'Transport')
            self.draw_button(screen, btn_name, label, color=BUTTON_BG)

            try:
                cap = int(getattr(t, "transport_capacity", 0))
                used = int(getattr(t, "transport_slots_used", 0))
                rem = int(getattr(t, "transport_slots_remaining", 0))
            except Exception:
                cap, used, rem = 0, 0, 0
            info = f"Capacity: {used}/{cap} (rem {rem})"
            info_surface = self.font_tiny.render(info, True, TEXT_SECONDARY)
            screen.blit(info_surface, (rect.x + 12, rect.y + rect.height - 18))

            if i == self.selected_transport_index:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        # Draw unit rows for selected transport
        t = self._selected_transport()
        candidates = self._candidates_for_transport(t)
        assigned = self.assignments.get(t, set()) if t is not None else set()
        for i, u in enumerate(candidates):
            btn_name = f"unit_{i}"
            if btn_name not in self.buttons:
                continue
            rect = self.buttons[btn_name]
            if btn_name in self.button_states:
                self.button_states[btn_name]['state'] = 'selected' if u in assigned else 'normal'

            label = getattr(u, "name", f"unit_{i}")
            self.draw_button(screen, btn_name, label, color=BUTTON_BG)

            try:
                slots = int(u.get_transport_slots_required())
            except Exception:
                slots = 0
            info = f"Slots: {slots}"
            info_surface = self.font_tiny.render(info, True, TEXT_SECONDARY)
            screen.blit(info_surface, (rect.x + 12, rect.y + rect.height - 18))

            if u in assigned:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        # Action buttons
        self.draw_button(screen, "confirm", "Done")
        self.draw_button(screen, "cancel", "Cancel")
