import pygame
from typing import Callable, Dict, List, Optional

from .base_dialog import (
    BaseDialog,
    PANEL_BG,
    PANEL_BORDER,
    BUTTON_BG,
    BUTTON_HOVER,
    BUTTON_DISABLED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_DISABLED,
)
from ...utility.entity_ids import get_entity_id


class MeleeTargetAllocationDialog(BaseDialog):
    """Dialog to assign each fighting model to an eligible melee target."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=720, height=520, draggable=True, center=True)
        self.unit = None
        self.target_units: List = []
        self.game_map = None
        self.on_confirm: Optional[Callable[[str, Dict[str, List[str]]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.decision_request = None
        self._option_entries: List[dict] = []

        self.model_assignments: Dict[object, Optional[object]] = {}
        self.eligible_targets_by_model: Dict[object, List[object]] = {}
        self.scroll_offset = 0
        self.max_scroll = 0
        self._row_height = 34

        self._models_cache: List[object] = []

    def show(
        self,
        unit,
        target_units: List,
        on_confirm: Callable[[str, Dict[str, List[str]]], None],
        game_map=None,
        on_cancel: Optional[Callable[[], None]] = None,
        decision_request=None,
    ) -> None:
        self.unit = unit
        self.target_units = list(target_units or [])
        self.game_map = game_map
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.decision_request = decision_request
        self._option_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)
        super().show()
        self._initialize_assignments()
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.unit = None
        self.target_units = []
        self.game_map = None
        self.on_confirm = None
        self.on_cancel = None
        self.model_assignments = {}
        self.eligible_targets_by_model = {}
        self.scroll_offset = 0
        self.max_scroll = 0
        self._models_cache = []
        self.decision_request = None
        self._option_entries = []

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()
        button_w, button_h = 120, 40
        self.add_button("confirm", self.width - button_w - 20, self.height - button_h - 16, button_w, button_h, True)
        self.add_button("cancel", 20, self.height - button_h - 16, button_w, button_h, True)

    def _initialize_assignments(self) -> None:
        self.model_assignments = {}
        self.eligible_targets_by_model = {}
        self._models_cache = []
        self.scroll_offset = 0

        if self.unit is None:
            return

        models = [m for m in list(getattr(self.unit, "models", []) or []) if getattr(m, "is_alive", True)]
        self._models_cache = models
        if not models or not self.target_units:
            return

        eligible_models_by_target: Dict[object, set] = {}
        allow_within_3 = False
        try:
            allow_within_3 = bool(self.unit.fight_within_3_active())
        except Exception:
            allow_within_3 = False

        for target in self.target_units:
            try:
                eligible = self.unit.get_fight_eligible_models_for_target(
                    target,
                    game_map=self.game_map,
                    allow_within_3=allow_within_3,
                )
            except Exception:
                eligible = models
            eligible_models_by_target[target] = set(eligible or [])

        for model in models:
            options = [t for t in self.target_units if model in eligible_models_by_target.get(t, set())]
            self.eligible_targets_by_model[model] = options
            if not options:
                self.model_assignments[model] = None
                continue
            self.model_assignments[model] = self._default_target_for_model(model, options)

        self._recalculate_scroll_bounds()

    def _default_target_for_model(self, model, options: List) -> object:
        if len(options) == 1:
            return options[0]
        try:
            from ...utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return options[0]

        best = None
        best_dist = float("inf")
        for target in options:
            try:
                target_models = [m for m in list(getattr(target, "models", []) or []) if getattr(m, "is_alive", True)]
            except Exception:
                target_models = []
            if not target_models:
                continue
            for tm in target_models:
                try:
                    dist = float(distance_between_models_bases_3d(model, tm))
                except Exception:
                    continue
                if dist < best_dist:
                    best_dist = dist
                    best = target
        return best or options[0]

    def _recalculate_scroll_bounds(self) -> None:
        list_height = self._list_area_height()
        content_height = len(self._models_cache) * self._row_height
        self.max_scroll = max(0, content_height - list_height)
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset))

    def _list_area_rect(self) -> pygame.Rect:
        list_x = self.x + 20
        list_y = self.y + self.title_bar_height + 60
        list_width = self.width - 40
        list_height = self._list_area_height()
        return pygame.Rect(list_x, list_y, list_width, list_height)

    def _list_area_height(self) -> int:
        return self.height - (self.title_bar_height + 60) - 70

    def _row_rects(self) -> List[tuple]:
        rows = []
        if not self._models_cache:
            return rows
        list_rect = self._list_area_rect()
        for idx, model in enumerate(self._models_cache):
            row_y = list_rect.y + idx * self._row_height - self.scroll_offset
            row_rect = pygame.Rect(list_rect.x, row_y, list_rect.width, self._row_height - 4)
            if row_rect.bottom < list_rect.top or row_rect.top > list_rect.bottom:
                continue
            rows.append((model, row_rect))
        return rows

    def _cycle_assignment(self, model) -> None:
        options = self.eligible_targets_by_model.get(model, [])
        if not options:
            return
        current = self.model_assignments.get(model)
        if current not in options:
            self.model_assignments[model] = options[0]
            return
        idx = options.index(current)
        self.model_assignments[model] = options[(idx + 1) % len(options)]

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True
        if button_name == "confirm":
            if self.on_confirm:
                option_id = self._option_entries[0]["option_id"] if self._option_entries else ""
                self.on_confirm(option_id, {"target_allocations": self._build_target_declarations()})
            self.hide()
            return True
        return False

    def _build_target_declarations(self) -> Dict[str, List[str]]:
        declarations: Dict[str, List[str]] = {}
        for model, target in self.model_assignments.items():
            if target is None:
                continue
            declarations.setdefault(get_entity_id(target), []).append(get_entity_id(model))
        return declarations

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if super().handle_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            delta = 30 if event.button == 5 else -30
            self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset + delta))
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            list_rect = self._list_area_rect()
            if list_rect.collidepoint(mouse_pos):
                for model, row_rect in self._row_rects():
                    if row_rect.collidepoint(mouse_pos):
                        if self.eligible_targets_by_model.get(model):
                            self._cycle_assignment(model)
                        return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        self.draw_dialog_background(screen)
        unit_name = getattr(self.unit, "name", "Unit")
        self.draw_title_bar(screen, f"Allocate Targets - {unit_name}")
        self.draw_instructions(screen, "Click a model to cycle its target.")

        list_rect = self._list_area_rect()
        pygame.draw.rect(screen, PANEL_BG, list_rect)
        pygame.draw.rect(screen, PANEL_BORDER, list_rect, 1)

        mouse_pos = pygame.mouse.get_pos()
        for model, row_rect in self._row_rects():
            options = self.eligible_targets_by_model.get(model, [])
            assigned = self.model_assignments.get(model)
            is_disabled = not options
            is_hover = row_rect.collidepoint(mouse_pos)
            if is_disabled:
                color = BUTTON_DISABLED
            else:
                color = BUTTON_HOVER if is_hover else BUTTON_BG
            pygame.draw.rect(screen, color, row_rect)
            pygame.draw.rect(screen, PANEL_BORDER, row_rect, 1)

            target_name = "Unassigned"
            if assigned is not None:
                target_name = getattr(assigned, "name", "Target")
            label = f"{getattr(model, 'name', 'Model')} -> {target_name}"
            text_color = TEXT_DISABLED if is_disabled else TEXT_PRIMARY
            text = self.font_small.render(label, True, text_color)
            screen.blit(text, (row_rect.x + 8, row_rect.y + 7))

        note = f"Targets: {', '.join(getattr(t, 'name', 'Target') for t in self.target_units)}"
        note_text = self.font_tiny.render(note, True, TEXT_SECONDARY)
        screen.blit(note_text, (list_rect.x, list_rect.bottom + 6))

        self.draw_button(screen, "confirm", "Confirm", color=BUTTON_BG)
        self.draw_button(screen, "cancel", "Cancel", color=BUTTON_BG)
