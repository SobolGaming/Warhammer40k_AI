from __future__ import annotations

from typing import Callable, Dict, List, Optional

import pygame

from .base_dialog import BaseDialog, PANEL_BG, PANEL_BORDER, BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY
from ...units.wargear import AttackCountInfo
from ...utility.entity_ids import get_entity_id


class MeleeAttackSplitDialog(BaseDialog):
    """Allocate a weapon bundle's attacks across multiple melee targets."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=560, height=420, draggable=True, center=True)
        self.unit = None
        self.weapon_bundle = None
        self.targets: List = []
        self.game_map = None
        self.attack_info: Optional[AttackCountInfo] = None
        self.allocations: Dict[object, int] = {}

        self.on_confirm: Optional[Callable[[Dict[object, int], AttackCountInfo], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.decision_request = None
        self._option_entries: List[dict] = []

        self._row_height = 44
        self._row_hitboxes: List[Dict[str, pygame.Rect]] = []

    def show(
        self,
        *,
        unit,
        weapon_bundle: dict,
        targets: List,
        game_map=None,
        attack_info: Optional[AttackCountInfo] = None,
        allocations: Optional[Dict[object, int]] = None,
        on_confirm: Callable[[str, Dict[str, object]], None],
        on_cancel: Optional[Callable[[], None]] = None,
        decision_request=None,
    ) -> None:
        self.unit = unit
        self.weapon_bundle = weapon_bundle
        self.targets = list(targets or [])
        self.game_map = game_map
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.decision_request = decision_request
        self._option_entries = []
        if self.decision_request is not None:
            from ..decision_ui_utils import option_entries

            self._option_entries = option_entries(self.decision_request)

        if attack_info is None:
            attack_info = self._roll_attack_count()
        self.attack_info = attack_info

        self.allocations = {}
        if allocations:
            for tgt in self.targets:
                if tgt in allocations:
                    self.allocations[tgt] = int(allocations[tgt] or 0)
        if not self.allocations and self.targets:
            self.allocations[self.targets[0]] = int(self._total_attacks())

        super().show(callback=None)
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.unit = None
        self.weapon_bundle = None
        self.targets = []
        self.game_map = None
        self.attack_info = None
        self.allocations = {}
        self.on_confirm = None
        self.on_cancel = None
        self._row_hitboxes = []
        self.decision_request = None
        self._option_entries = []

    def _roll_attack_count(self) -> AttackCountInfo:
        if not self.weapon_bundle or not self.targets:
            return AttackCountInfo(num_attacks=0, dice_rolls=[], special_modifiers=[])
        profile = self.weapon_bundle.get("weapon_profile")
        model = self.weapon_bundle.get("model")
        if profile is None or model is None:
            return AttackCountInfo(num_attacks=0, dice_rolls=[], special_modifiers=[])
        try:
            return profile.preview_attack_count(self.targets[0], model, game_map=self.game_map)
        except Exception:
            return AttackCountInfo(num_attacks=0, dice_rolls=[], special_modifiers=[])

    def _total_attacks(self) -> int:
        try:
            return int(getattr(self.attack_info, "num_attacks", 0) or 0)
        except Exception:
            return 0

    def _remaining_attacks(self) -> int:
        total = self._total_attacks()
        spent = 0
        for val in self.allocations.values():
            try:
                spent += int(val or 0)
            except Exception:
                pass
        return max(0, total - spent)

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()
        bw, bh = 150, 40
        gap = 16
        x = (self.width - (2 * bw + gap)) // 2
        y = self.height - 60
        can_confirm = bool(self._remaining_attacks() == 0)
        self.add_button("confirm", x, y, bw, bh, enabled=can_confirm)
        self.add_button("cancel", x + bw + gap, y, bw, bh, enabled=True)

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if callable(self.on_cancel):
                self.on_cancel()
            self.hide()
            return True
        if button_name == "confirm":
            if self._remaining_attacks() != 0:
                return True
            if callable(self.on_confirm) and self.attack_info is not None:
                option_id = self._option_entries[0]["option_id"] if self._option_entries else ""
                allocations = {get_entity_id(t): int(c or 0) for t, c in dict(self.allocations).items()}
                payload = {
                    "split_allocations": allocations,
                    "attack_info": self._serialize_attack_info(self.attack_info),
                }
                self.on_confirm(option_id, payload)
            self.hide()
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        for idx, hitbox in enumerate(self._row_hitboxes):
            if hitbox["minus"].collidepoint(mouse_pos):
                self._adjust_allocation(idx, -1)
                return True
            if hitbox["plus"].collidepoint(mouse_pos):
                self._adjust_allocation(idx, 1)
                return True
        return False

    def _adjust_allocation(self, idx: int, delta: int) -> None:
        if idx < 0 or idx >= len(self.targets):
            return
        target = self.targets[idx]
        current = int(self.allocations.get(target, 0) or 0)
        if delta > 0 and self._remaining_attacks() <= 0:
            return
        new_val = max(0, current + int(delta))
        self.allocations[target] = new_val
        self._create_buttons()

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        title = "Split Melee Attacks"
        self.draw_title_bar(screen, title)

        bundle_label = "Weapon"
        try:
            model = self.weapon_bundle.get("model")
            profile = self.weapon_bundle.get("weapon_profile")
            wargear = self.weapon_bundle.get("wargear")
            if wargear is not None:
                bundle_label = wargear.name
            if profile is not None and getattr(profile, "name", "default") != "default":
                bundle_label = f"{bundle_label} - {profile.name}"
            if model is not None:
                bundle_label = f"{model.name}: {bundle_label}"
        except Exception:
            pass

        info_y = self.y + self.title_bar_height + 16
        info_text = self.font_small.render(bundle_label, True, TEXT_PRIMARY)
        screen.blit(info_text, (self.x + 20, info_y))

        total = self._total_attacks()
        rolls = ""
        if self.attack_info and self.attack_info.dice_rolls:
            rolls = f" (rolls: {self.attack_info.dice_rolls})"
        count_text = self.font_small.render(f"Total attacks: {total}{rolls}", True, TEXT_SECONDARY)
        screen.blit(count_text, (self.x + 20, info_y + 20))

        remaining = self._remaining_attacks()
        rem_text = self.font_small.render(f"Remaining: {remaining}", True, TEXT_SECONDARY)
        screen.blit(rem_text, (self.x + 20, info_y + 40))

        list_x = self.x + 20
        list_y = info_y + 70
        list_w = self.width - 40
        list_h = self.height - list_y - 80
        list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        pygame.draw.rect(screen, PANEL_BG, list_rect)
        pygame.draw.rect(screen, PANEL_BORDER, list_rect, 1)

        self._row_hitboxes = []
        for idx, target in enumerate(self.targets):
            row_y = list_y + idx * self._row_height
            row_rect = pygame.Rect(list_x, row_y, list_w, self._row_height - 4)
            if row_rect.bottom < list_rect.top or row_rect.top > list_rect.bottom:
                continue
            pygame.draw.rect(screen, BUTTON_BG, row_rect)
            pygame.draw.rect(screen, PANEL_BORDER, row_rect, 1)

            name = getattr(target, "name", "Target")
            name_surf = self.font_small.render(name, True, TEXT_PRIMARY)
            screen.blit(name_surf, (row_rect.x + 8, row_rect.y + 10))

            count_val = int(self.allocations.get(target, 0) or 0)
            count_surf = self.font_small.render(str(count_val), True, TEXT_PRIMARY)
            screen.blit(count_surf, (row_rect.right - 90, row_rect.y + 10))

            minus_rect = pygame.Rect(row_rect.right - 130, row_rect.y + 8, 24, 24)
            plus_rect = pygame.Rect(row_rect.right - 40, row_rect.y + 8, 24, 24)

            for rect, label in ((minus_rect, "-"), (plus_rect, "+")):
                pygame.draw.rect(screen, BUTTON_HOVER, rect)
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1)
                txt = self.font_small.render(label, True, TEXT_PRIMARY)
                screen.blit(txt, (rect.x + 7, rect.y + 2))

            self._row_hitboxes.append({"minus": minus_rect, "plus": plus_rect})

        self._create_buttons()
        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")

    def _serialize_attack_info(self, info: AttackCountInfo) -> Dict[str, object]:
        return {
            "num_attacks": int(getattr(info, "num_attacks", 0) or 0),
            "dice_rolls": list(getattr(info, "dice_rolls", []) or []),
            "special_modifiers": list(getattr(info, "special_modifiers", []) or []),
        }
