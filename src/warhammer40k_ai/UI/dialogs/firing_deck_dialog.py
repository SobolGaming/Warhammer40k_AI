import pygame
from typing import Callable, Dict, List, Optional, Set

from .base_dialog import BaseDialog, BUTTON_BG, PANEL_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_SELECTED
import logging
logger = logging.getLogger(__name__)


class FiringDeckDialog(BaseDialog):
    """
    Dialog for selecting up to X embarked models' ranged weapons to fire via a transport's Firing Deck X.

    - Lists non-ONE SHOT ranged weapons carried by embarked models.
    - To save space, shows at most X entries per (wargear name, profile name) across embarked models.
    - Enforces: at most X total selections AND at most 1 selected weapon per embarked model.
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=760, height=520, draggable=True, center=True)
        self.transport_unit = None
        self.firing_deck_x: int = 0
        self.entries: List[Dict] = []
        self.selected_indices: Set[int] = set()
        self.on_confirm: Optional[Callable[[List[Dict]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.decision_request = None

        # Scrolling
        self.scroll_offset = 0
        self.max_scroll = 0

    def show(
        self,
        transport_unit,
        firing_deck_x: int,
        entries: List[Dict],
        on_confirm: Callable[[str, Dict], None],
        on_cancel: Optional[Callable[[], None]] = None,
        *,
        decision_request=None,
    ) -> None:
        self.transport_unit = transport_unit
        self.firing_deck_x = int(firing_deck_x or 0)
        self.entries = list(entries or [])
        self.selected_indices = set()
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.decision_request = decision_request
        self.scroll_offset = 0
        super().show()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.transport_unit = None
        self.firing_deck_x = 0
        self.entries = []
        self.selected_indices = set()
        self.on_confirm = None
        self.on_cancel = None
        self.decision_request = None
        self.scroll_offset = 0
        self.max_scroll = 0

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

        # Row buttons
        button_width = self.width - 40
        button_height = 50
        button_spacing = 8
        start_y_rel = self.title_bar_height + 84

        for i, _e in enumerate(self.entries):
            rel_y = start_y_rel + i * (button_height + button_spacing) - self.scroll_offset
            if rel_y + button_height < self.title_bar_height + 70 or rel_y > self.height - 80:
                continue
            self.add_button(f"entry_{i}", 20, rel_y, button_width, button_height, enabled=True)

        total_height = len(self.entries) * (button_height + button_spacing)
        available_height = self.height - (self.title_bar_height + 150)
        self.max_scroll = max(0, total_height - available_height)

        # Actions
        self.add_button("confirm", self.width - 280, self.height - 55, 120, 38, enabled=True)
        self.add_button("cancel", self.width - 150, self.height - 55, 120, 38, enabled=True)

    def _selected_model_ids(self) -> Set[str]:
        mids: Set[str] = set()
        for idx in self.selected_indices:
            if 0 <= idx < len(self.entries):
                m = self.entries[idx].get("model")
                if m is not None:
                    mids.add(m.id)
        return mids

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True

        if button_name == "confirm":
            option_id = self._option_id_for_action("confirm")
            if option_id and self.on_confirm:
                self.on_confirm(option_id, {"selected_entries": self._build_selected_payload()})
            self.hide()
            return True

        if button_name.startswith("entry_"):
            try:
                idx = int(button_name.split("_", 1)[1])
            except Exception:
                return False
            if not (0 <= idx < len(self.entries)):
                return False

            # Toggle off
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
                return True

            # Enforce total cap
            if len(self.selected_indices) >= int(self.firing_deck_x or 0):
                logger.info(f"INFO: Firing Deck: you can select at most {self.firing_deck_x} embarked models.")
                return True

            # Enforce: one weapon per embarked model
            entry = self.entries[idx]
            m = entry.get("model")
            if m is not None and m.id in self._selected_model_ids():
                logger.error("ERROR: Firing Deck: that embarked model is already selected (one weapon per model).")
                return True

            self.selected_indices.add(idx)
            return True

        return False

    def _option_id_for_action(self, action: str) -> str:
        from ..decision_ui_utils import option_id_for_action

        return option_id_for_action(self.decision_request, action)

    def _build_selected_payload(self) -> List[Dict]:
        try:
            from ...utility.entity_ids import get_entity_id
        except Exception:
            get_entity_id = None
        entries_payload: List[Dict] = []
        for i in sorted(self.selected_indices):
            if not (0 <= i < len(self.entries)):
                continue
            entry = self.entries[i]
            model = entry.get("model")
            wargear = entry.get("wargear")
            profile_name = entry.get("profile_name")
            if get_entity_id is None or model is None or wargear is None or not profile_name:
                continue
            entries_payload.append(
                {
                    "model_id": get_entity_id(model),
                    "wargear_id": get_entity_id(wargear),
                    "profile_name": str(profile_name),
                }
            )
        return entries_payload

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        tname = getattr(self.transport_unit, "name", "Transport")
        subtitle = f"Select up to {self.firing_deck_x} embarked models' weapons"
        self.draw_title_bar(screen, f"Firing Deck - {tname}", subtitle=subtitle)

        # Instructions
        inst = "Pick up to X non-ONE SHOT ranged weapons from embarked models (max 1 per model)."
        inst_surface = self.font_small.render(inst, True, TEXT_SECONDARY)
        screen.blit(inst_surface, (self.x + 20, self.y + self.title_bar_height + 10))

        # Counter
        counter = f"Selected: {len(self.selected_indices)}/{self.firing_deck_x}"
        counter_surface = self.font_small.render(counter, True, TEXT_PRIMARY)
        screen.blit(counter_surface, (self.x + 20, self.y + self.title_bar_height + 34))

        # Update visible buttons (scroll-aware)
        self._create_buttons()
        self._update_buttons()

        for i, e in enumerate(self.entries):
            btn_name = f"entry_{i}"
            if btn_name not in self.buttons:
                continue

            if btn_name in self.button_states:
                self.button_states[btn_name]["state"] = "selected" if i in self.selected_indices else "normal"

            rect = self.buttons[btn_name]
            model = e.get("model")
            profile = e.get("profile")
            wargear = e.get("wargear")
            profile_name = e.get("profile_name") or getattr(profile, "name", "default")
            wname = getattr(wargear, "name", "Weapon")
            mname = getattr(model, "name", "Model")

            line1 = f"{wname} ({profile_name})"
            line2 = f"From: {mname}"

            # Button background
            self.draw_button(screen, btn_name, "", color=BUTTON_BG)

            # Text
            t1 = self.font_small.render(line1, True, TEXT_PRIMARY)
            t2 = self.font_tiny.render(line2, True, TEXT_SECONDARY)
            screen.blit(t1, (rect.x + 12, rect.y + 10))
            screen.blit(t2, (rect.x + 12, rect.y + 30))

            # Outline
            if i in self.selected_indices:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 2)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)

        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")


