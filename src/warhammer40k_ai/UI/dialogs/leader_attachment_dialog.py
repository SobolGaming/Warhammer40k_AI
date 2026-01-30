import pygame
from typing import Callable, Dict, List, Optional, Tuple

from warhammer40k_ai.utility.entity_ids import get_entity_id

from .base_dialog import BaseDialog, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_WARNING, BUTTON_SELECTED


class LeaderAttachmentDialog(BaseDialog):
    """
    Declare Battle Formations dialog: attach/detach Leaders to eligible Bodyguard units.

    UX:
    - Left column: Leaders (select one)
    - Right column: Eligible targets for selected leader (including "Unattached")
    - Bottom: Done / Cancel
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=820, height=520, draggable=True, center=True)
        self.title = "Attach Leaders (Declare Battle Formations)"
        self.subtitle = "Select a Leader, then choose an eligible unit to attach (or Unattached)."
        self.left_label = "Leaders"
        self.right_label = "Eligible Bodyguard Units"

        self.army_units: List = []
        self.leaders: List = []
        self.bodyguards: List = []
        self.decision_requests: Dict[str, object] = {}
        self._selected_option_ids: Dict[str, str] = {}

        self.selected_leader_idx: Optional[int] = None
        self.target_rows: List[Tuple[str, Optional[object]]] = []  # (label, unit or None)
        self.selected_target_idx: Optional[int] = None

        self.on_confirm: Optional[Callable[[Dict[str, str]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        # Scrolling
        self.leader_scroll = 0
        self.target_scroll = 0
        self._leader_max_scroll = 0
        self._target_max_scroll = 0

        # Cached message line
        self._message: str = ""
        self._message_color = TEXT_SECONDARY

        # Display names (disambiguate duplicate unit names like "Warp Spiders 1")
        self._unit_display_names = {}

    def show(
        self,
        army_units: List,
        *,
        leader_requests: Dict[str, object],
        on_confirm: Callable[[Dict[str, str]], None],
        on_cancel: Optional[Callable[[], None]] = None,
        leaders: Optional[List] = None,
        bodyguards: Optional[List] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        left_label: Optional[str] = None,
        right_label: Optional[str] = None,
    ) -> None:
        self.army_units = list(army_units or [])
        # Reset defaults every time (support artillery override may set custom labels)
        self.title = "Attach Leaders (Declare Battle Formations)"
        self.subtitle = "Select a Leader, then choose an eligible unit to attach (or Unattached)."
        self.left_label = "Leaders"
        self.right_label = "Eligible Bodyguard Units"
        if leaders is not None:
            self.leaders = list(leaders or [])
        else:
            self.leaders = [u for u in self.army_units if bool(getattr(u, "is_leader", False))]
        if bodyguards is not None:
            self.bodyguards = list(bodyguards or [])
        else:
            self.bodyguards = [u for u in self.army_units if not bool(getattr(u, "is_leader", False))]
        if title is not None:
            self.title = title
        if subtitle is not None:
            self.subtitle = subtitle
        if left_label is not None:
            self.left_label = left_label
        if right_label is not None:
            self.right_label = right_label
        self._recompute_display_names()
        self.selected_leader_idx = 0 if self.leaders else None
        self.leader_scroll = 0
        self.target_scroll = 0
        self.decision_requests = dict(leader_requests or {})
        self._selected_option_ids = self._seed_selected_options()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._message = ""
        self._message_color = TEXT_SECONDARY
        super().show()
        self._rebuild_targets()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.army_units = []
        self.leaders = []
        self.bodyguards = []
        self._unit_display_names = {}
        self.decision_requests = {}
        self._selected_option_ids = {}
        self.selected_leader_idx = None
        self.target_rows = []
        self.selected_target_idx = None
        self.on_confirm = None
        self.on_cancel = None
        self._message = ""
        self._message_color = TEXT_SECONDARY

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        # Scroll
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                # wheel up: scroll whichever list the cursor is over
                mx, my = event.pos
                if self._leader_list_rect().collidepoint((mx, my)):
                    self.leader_scroll = max(0, self.leader_scroll - 20)
                    return True
                if self._target_list_rect().collidepoint((mx, my)):
                    self.target_scroll = max(0, self.target_scroll - 20)
                    return True
            if event.button == 5:
                mx, my = event.pos
                if self._leader_list_rect().collidepoint((mx, my)):
                    self.leader_scroll = min(self._leader_max_scroll, self.leader_scroll + 20)
                    return True
                if self._target_list_rect().collidepoint((mx, my)):
                    self.target_scroll = min(self._target_max_scroll, self.target_scroll + 20)
                    return True

        if super().handle_event(event):
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        # Clicks within dialog: leaders list or targets list
        if self._leader_list_rect().collidepoint(mouse_pos):
            idx = self._row_index_from_click(mouse_pos, self._leader_list_rect(), row_h=44, scroll=self.leader_scroll)
            if idx is not None and 0 <= idx < len(self.leaders):
                self.selected_leader_idx = idx
                self._rebuild_targets()
                self._create_buttons()
                return True
            return True

        if self._target_list_rect().collidepoint(mouse_pos):
            idx = self._row_index_from_click(mouse_pos, self._target_list_rect(), row_h=44, scroll=self.target_scroll)
            if idx is not None and 0 <= idx < len(self.target_rows):
                self.selected_target_idx = idx
                label, target_unit = self.target_rows[idx]
                self._apply_selection(target_unit)
                self._rebuild_targets()
                self._create_buttons()
                return True
            return True

        return False

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True
        if button_name == "done":
            if self.on_confirm:
                self.on_confirm(dict(self._selected_option_ids))
            self.hide()
            return True
        return False

    def _leader_list_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x + 20, self.y + self.title_bar_height + 60, 360, 320)

    def _target_list_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x + 400, self.y + self.title_bar_height + 60, 400, 320)

    def _row_index_from_click(self, mouse_pos, list_rect: pygame.Rect, row_h: int, scroll: int) -> Optional[int]:
        mx, my = mouse_pos
        rel_y = my - list_rect.y + scroll
        if rel_y < 0:
            return None
        return int(rel_y // row_h)

    def _rebuild_targets(self) -> None:
        self.target_rows = []
        self.selected_target_idx = None

        if self.selected_leader_idx is None or not (0 <= self.selected_leader_idx < len(self.leaders)):
            return
        leader = self.leaders[self.selected_leader_idx]
        leader_id = get_entity_id(leader)
        request = self.decision_requests.get(leader_id)
        options = list(getattr(request, "options", []) or []) if request is not None else []
        selected_option_id = self._selected_option_ids.get(leader_id)

        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            bodyguard_id = payload.get("bodyguard_id")
            target_unit = None
            if bodyguard_id:
                target_unit = next((u for u in self.bodyguards if get_entity_id(u) == str(bodyguard_id)), None)
            label = str(getattr(opt, "label", "Option"))
            if target_unit is not None:
                label = self._get_display_name(target_unit)
            if opt.option_id == selected_option_id:
                label = f"[x] {label}"
                self.selected_target_idx = len(self.target_rows)
            self.target_rows.append((label, target_unit))

        # Update scroll bounds
        self._recompute_scroll_bounds()

    def _recompute_scroll_bounds(self) -> None:
        # Leader list
        leader_visible_h = self._leader_list_rect().height
        leader_total_h = len(self.leaders) * 44
        self._leader_max_scroll = max(0, leader_total_h - leader_visible_h)
        self.leader_scroll = max(0, min(self._leader_max_scroll, self.leader_scroll))
        # Target list
        target_visible_h = self._target_list_rect().height
        target_total_h = len(self.target_rows) * 44
        self._target_max_scroll = max(0, target_total_h - target_visible_h)
        self.target_scroll = max(0, min(self._target_max_scroll, self.target_scroll))

    def _apply_selection(self, target_unit) -> None:
        if self.selected_leader_idx is None or not (0 <= self.selected_leader_idx < len(self.leaders)):
            return
        leader = self.leaders[self.selected_leader_idx]
        leader_id = get_entity_id(leader)
        request = self.decision_requests.get(leader_id)
        options = list(getattr(request, "options", []) or []) if request is not None else []
        chosen = None
        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            bodyguard_id = payload.get("bodyguard_id")
            if bodyguard_id is None and target_unit is None:
                chosen = opt
                break
            if target_unit is not None and str(bodyguard_id or "") == get_entity_id(target_unit):
                chosen = opt
                break
        if chosen is None:
            self._message = "Invalid selection"
            self._message_color = TEXT_WARNING
            return
        self._selected_option_ids[leader_id] = chosen.option_id
        if target_unit is None:
            self._message = f"{leader.name}: set to Unattached"
        else:
            self._message = f"{leader.name}: attached to {self._get_display_name(target_unit)}"
        self._message_color = TEXT_SECONDARY

    def _seed_selected_options(self) -> Dict[str, str]:
        selected: Dict[str, str] = {}
        for leader in self.leaders:
            leader_id = get_entity_id(leader)
            request = self.decision_requests.get(leader_id)
            options = list(getattr(request, "options", []) or []) if request is not None else []
            attached = getattr(leader, "get_attachment_target", lambda: getattr(leader, "attached_to", None))()
            attached_id = get_entity_id(attached) if attached is not None else None
            chosen = None
            for opt in options:
                payload = dict(getattr(opt, "payload", {}) or {})
                bodyguard_id = payload.get("bodyguard_id")
                if attached_id is None and bodyguard_id is None:
                    chosen = opt
                    break
                if attached_id is not None and str(bodyguard_id or "") == attached_id:
                    chosen = opt
                    break
            if chosen is None and options:
                chosen = options[0]
            if chosen is not None:
                selected[leader_id] = chosen.option_id
        return selected

    def _recompute_display_names(self) -> None:
        """
        Compute roster-like disambiguated names per-army:
        if multiple units share a name within the same army, enumerate them: "Name 1", "Name 2", ...
        """
        self._unit_display_names = {}
        try:
            def _army_key(u):
                try:
                    a = u.get_parent_army()
                    return get_entity_id(a)
                except Exception:
                    return "no_army"

            # Count duplicates per (army, name)
            name_counts = {}
            for u in self.army_units:
                nm = getattr(u, "name", "")
                key = (_army_key(u), nm)
                name_counts[key] = name_counts.get(key, 0) + 1

            # Enumerate in provided order (stable)
            running = {}
            for u in self.army_units:
                nm = getattr(u, "name", "")
                uid = get_entity_id(u)
                key = (_army_key(u), nm)
                if name_counts.get(key, 0) > 1:
                    running[key] = running.get(key, 0) + 1
                    self._unit_display_names[uid] = f"{nm} {running[key]}"
                else:
                    self._unit_display_names[uid] = nm
        except Exception:
            self._unit_display_names = {}

    def _get_display_name(self, unit) -> str:
        try:
            uid = get_entity_id(unit)
            return self._unit_display_names.get(uid, getattr(unit, "name", "Unit"))
        except Exception:
            return getattr(unit, "name", "Unit")

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()

        # Bottom buttons
        self.add_button("done", self.width - 260, self.height - 55, 110, 38, enabled=True)
        self.add_button("cancel", self.width - 140, self.height - 55, 110, 38, enabled=True)

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        self.draw_title_bar(screen, self.title, subtitle=self.subtitle)

        # Sections
        header = self.font_medium.render(self.left_label, True, TEXT_PRIMARY)
        screen.blit(header, (self.x + 20, self.y + self.title_bar_height + 30))
        header2 = self.font_medium.render(self.right_label, True, TEXT_PRIMARY)
        screen.blit(header2, (self.x + 400, self.y + self.title_bar_height + 30))

        leader_rect = self._leader_list_rect()
        target_rect = self._target_list_rect()
        pygame.draw.rect(screen, (30, 30, 34), leader_rect)
        pygame.draw.rect(screen, PANEL_BORDER, leader_rect, 1)
        pygame.draw.rect(screen, (30, 30, 34), target_rect)
        pygame.draw.rect(screen, PANEL_BORDER, target_rect, 1)

        # Draw leader rows
        row_h = 44
        start_i = int(self.leader_scroll // row_h)
        y0 = leader_rect.y - (self.leader_scroll % row_h)
        for i in range(start_i, len(self.leaders)):
            y = y0 + (i - start_i) * row_h
            if y > leader_rect.bottom:
                break
            rect = pygame.Rect(leader_rect.x + 6, y + 4, leader_rect.width - 12, row_h - 8)
            if i == self.selected_leader_idx:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)
            leader = self.leaders[i]
            attached_to = getattr(leader, "get_attachment_target", lambda: getattr(leader, "attached_to", None))()
            # ASCII-only arrow for broad font support
            status = f" -> {self._get_display_name(attached_to)}" if attached_to is not None else ""
            txt = self.font_small.render(f"{self._get_display_name(leader)}{status}", True, TEXT_SECONDARY)
            screen.blit(txt, (rect.x + 10, rect.y + 12))

        # Draw target rows
        start_i = int(self.target_scroll // row_h)
        y0 = target_rect.y - (self.target_scroll % row_h)
        for i in range(start_i, len(self.target_rows)):
            y = y0 + (i - start_i) * row_h
            if y > target_rect.bottom:
                break
            rect = pygame.Rect(target_rect.x + 6, y + 4, target_rect.width - 12, row_h - 8)
            if i == self.selected_target_idx:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)
            label, _unit = self.target_rows[i]
            txt = self.font_small.render(label, True, TEXT_SECONDARY)
            screen.blit(txt, (rect.x + 10, rect.y + 12))

        # Message line
        if self._message:
            msg = self.font_tiny.render(self._message, True, self._message_color)
            screen.blit(msg, (self.x + 20, self.y + self.height - 58))

        # Buttons
        self._update_buttons()
        self.draw_button(screen, "done", "Done")
        self.draw_button(screen, "cancel", "Cancel")
