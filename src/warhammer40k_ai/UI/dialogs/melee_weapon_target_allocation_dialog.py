from __future__ import annotations

from typing import Callable, Dict, List, Optional

import pygame

from .base_dialog import (
    BaseDialog,
    PANEL_BG,
    PANEL_BORDER,
    BUTTON_BG,
    BUTTON_HOVER,
    BUTTON_SELECTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_DISABLED,
)
from ...units.wargear import AttackCountInfo


class MeleeWeaponTargetAllocationDialog(BaseDialog):
    """Assign melee weapon bundles to targets, with optional attack splits."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        super().__init__(screen_width, screen_height, width=760, height=560, draggable=True, center=True)
        self.unit = None
        self.target_units: List = []
        self.weapon_bundles: List[dict] = []
        self.game_map = None
        self.split_dialog = None

        self.on_confirm: Optional[Callable[[List[dict]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.scroll_offset = 0
        self.max_scroll = 0
        self._row_height = 50

        self._row_hitboxes: List[Dict[str, pygame.Rect]] = []

    def show(
        self,
        unit,
        target_units: List,
        weapon_declarations: List[dict],
        on_confirm: Callable[[List[dict]], None],
        game_map=None,
        on_cancel: Optional[Callable[[], None]] = None,
        *,
        split_dialog=None,
    ) -> None:
        self.unit = unit
        self.target_units = list(target_units or [])
        self.game_map = game_map
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.split_dialog = split_dialog

        self.scroll_offset = 0
        self._build_bundles(list(weapon_declarations or []))
        super().show(callback=None)
        self._create_buttons()

    def hide(self) -> None:
        super().hide()
        self.unit = None
        self.target_units = []
        self.weapon_bundles = []
        self.game_map = None
        self.on_confirm = None
        self.on_cancel = None
        self.split_dialog = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self._row_hitboxes = []

    def _build_bundles(self, weapon_declarations: List[dict]) -> None:
        self.weapon_bundles = []
        if not self.unit:
            return

        allow_within_3 = False
        try:
            if hasattr(self.unit, "has_fight_within_3_ability") and self.unit.has_fight_within_3_ability():
                allow_within_3 = bool(self.unit.fight_within_3_active())
        except Exception:
            allow_within_3 = False

        eligible_by_target: Dict[object, set] = {}
        for target in self.target_units:
            try:
                eligible = self.unit.get_fight_eligible_models_for_target(
                    target,
                    game_map=self.game_map,
                    allow_within_3=allow_within_3,
                )
            except Exception:
                eligible = []
            eligible_by_target[target] = set(eligible or [])

        for decl in weapon_declarations:
            model = decl.get("model")
            profile = decl.get("weapon_profile")
            if model is None or profile is None:
                continue
            eligible_targets = [t for t in self.target_units if model in eligible_by_target.get(t, set())]
            selected_target = eligible_targets[0] if eligible_targets else None
            self.weapon_bundles.append({
                "model": model,
                "weapon_profile": profile,
                "wargear": decl.get("wargear"),
                "profile_name": decl.get("profile_name"),
                "eligible_targets": eligible_targets,
                "selected_target": selected_target,
                "split_allocations": None,
                "split_attack_info": None,
            })

        content_height = len(self.weapon_bundles) * self._row_height
        visible_height = self.height - (self.title_bar_height + 120)
        self.max_scroll = max(0, content_height - visible_height)

    def _create_buttons(self) -> None:
        self.buttons.clear()
        self.button_states.clear()
        bw, bh = 140, 40
        gap = 16
        x = (self.width - (2 * bw + gap)) // 2
        y = self.height - 60
        self.add_button("confirm", x, y, bw, bh, enabled=self._can_confirm())
        self.add_button("cancel", x + bw + gap, y, bw, bh, enabled=True)

    def _can_confirm(self) -> bool:
        for bundle in self.weapon_bundles:
            eligible = bundle.get("eligible_targets") or []
            if not eligible:
                continue
            if bundle.get("split_allocations"):
                continue
            if bundle.get("selected_target") is None:
                return False
        return True

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name == "cancel":
            if callable(self.on_cancel):
                self.on_cancel()
            self.hide()
            return True
        if button_name == "confirm":
            if not self._can_confirm():
                return True
            if callable(self.on_confirm):
                self.on_confirm(self._build_attack_declarations())
            self.hide()
            return True
        return False

    def _build_attack_declarations(self) -> List[dict]:
        declarations: List[dict] = []
        for bundle in self.weapon_bundles:
            model = bundle.get("model")
            profile = bundle.get("weapon_profile")
            if model is None or profile is None:
                continue
            if bundle.get("split_allocations"):
                attack_info: Optional[AttackCountInfo] = bundle.get("split_attack_info")
                total = int(getattr(attack_info, "num_attacks", 0) or 0) if attack_info else 0
                mods = list(getattr(attack_info, "special_modifiers", []) or []) if attack_info else []
                for target, count in bundle["split_allocations"].items():
                    if count <= 0:
                        continue
                    note = f"Split {int(count)} of {int(total)}"
                    declarations.append({
                        "model": model,
                        "weapon_profile": profile,
                        "wargear": bundle.get("wargear"),
                        "profile_name": bundle.get("profile_name"),
                        "target_unit": target,
                        "attacks_override": int(count),
                        "attacks_override_modifiers": mods,
                        "attacks_override_note": note,
                    })
                continue
            target = bundle.get("selected_target")
            if target is None:
                continue
            declarations.append({
                "model": model,
                "weapon_profile": profile,
                "wargear": bundle.get("wargear"),
                "profile_name": bundle.get("profile_name"),
                "target_unit": target,
            })
        return declarations

    def _open_split_dialog(self, bundle_idx: int) -> None:
        if self.split_dialog is None:
            return
        if bundle_idx < 0 or bundle_idx >= len(self.weapon_bundles):
            return
        bundle = self.weapon_bundles[bundle_idx]
        eligible_targets = bundle.get("eligible_targets") or []
        if len(eligible_targets) < 2:
            return

        def _on_confirm(allocations: Dict[object, int], attack_info: AttackCountInfo):
            bundle["split_allocations"] = dict(allocations)
            bundle["split_attack_info"] = attack_info
            bundle["selected_target"] = None
            self._create_buttons()

        def _on_cancel():
            pass

        self.split_dialog.show(
            unit=self.unit,
            weapon_bundle=bundle,
            targets=eligible_targets,
            game_map=self.game_map,
            attack_info=bundle.get("split_attack_info"),
            allocations=bundle.get("split_allocations"),
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
        )

    def _cycle_target(self, bundle_idx: int) -> None:
        if bundle_idx < 0 or bundle_idx >= len(self.weapon_bundles):
            return
        bundle = self.weapon_bundles[bundle_idx]
        if bundle.get("split_allocations"):
            return
        eligible = bundle.get("eligible_targets") or []
        if not eligible:
            return
        current = bundle.get("selected_target")
        if current not in eligible:
            bundle["selected_target"] = eligible[0]
            return
        idx = eligible.index(current)
        bundle["selected_target"] = eligible[(idx + 1) % len(eligible)]

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
            for idx, hitbox in enumerate(self._row_hitboxes):
                if hitbox["split"].collidepoint(mouse_pos):
                    self._open_split_dialog(idx)
                    return True
                if hitbox["row"].collidepoint(mouse_pos):
                    self._cycle_target(idx)
                    self._create_buttons()
                    return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        self.draw_dialog_background(screen)
        unit_name = getattr(self.unit, "name", "Unit")
        self.draw_title_bar(screen, f"Allocate Melee Targets - {unit_name}")
        self.draw_instructions(screen, "Click a row to cycle target. Use Split to allocate attacks across targets.")

        list_x = self.x + 20
        list_y = self.y + self.title_bar_height + 60
        list_w = self.width - 40
        list_h = self.height - (self.title_bar_height + 60) - 80
        list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        pygame.draw.rect(screen, PANEL_BG, list_rect)
        pygame.draw.rect(screen, PANEL_BORDER, list_rect, 1)

        self._row_hitboxes = []
        mouse_pos = pygame.mouse.get_pos()
        for idx, bundle in enumerate(self.weapon_bundles):
            row_y = list_y + idx * self._row_height - self.scroll_offset
            row_rect = pygame.Rect(list_x, row_y, list_w, self._row_height - 4)
            if row_rect.bottom < list_rect.top or row_rect.top > list_rect.bottom:
                continue

            is_hover = row_rect.collidepoint(mouse_pos)
            row_color = BUTTON_HOVER if is_hover else BUTTON_BG
            pygame.draw.rect(screen, row_color, row_rect)
            pygame.draw.rect(screen, PANEL_BORDER, row_rect, 1)

            model = bundle.get("model")
            profile = bundle.get("weapon_profile")
            wargear = bundle.get("wargear")
            weapon_name = getattr(wargear, "name", "Weapon")
            if profile is not None and getattr(profile, "name", "default") != "default":
                weapon_name = f"{weapon_name} - {profile.name}"
            model_name = getattr(model, "name", "Model")
            left_text = f"{model_name}: {weapon_name}"
            left_surf = self.font_small.render(left_text, True, TEXT_PRIMARY)
            screen.blit(left_surf, (row_rect.x + 6, row_rect.y + 6))

            eligible_targets = bundle.get("eligible_targets") or []
            status_text = "No targets"
            status_color = TEXT_DISABLED
            if bundle.get("split_allocations"):
                parts = []
                for t, count in bundle["split_allocations"].items():
                    parts.append(f"{getattr(t, 'name', 'Target')}:{int(count)}")
                status_text = "Split: " + ", ".join(parts) if parts else "Split"
                status_color = TEXT_SECONDARY
            elif eligible_targets:
                target = bundle.get("selected_target")
                if target is not None:
                    status_text = f"Target: {getattr(target, 'name', 'Target')}"
                    status_color = TEXT_SECONDARY
                else:
                    status_text = "Target: Unassigned"
                    status_color = TEXT_DISABLED

            status_surf = self.font_small.render(status_text, True, status_color)
            screen.blit(status_surf, (row_rect.x + 6, row_rect.y + 26))

            split_rect = pygame.Rect(row_rect.right - 80, row_rect.y + 8, 70, 28)
            can_split = len(eligible_targets) > 1
            split_color = BUTTON_SELECTED if bundle.get("split_allocations") else BUTTON_BG
            if can_split:
                pygame.draw.rect(screen, split_color, split_rect)
                pygame.draw.rect(screen, PANEL_BORDER, split_rect, 1)
                split_label = "Split"
                split_surf = self.font_small.render(split_label, True, TEXT_PRIMARY)
                screen.blit(split_surf, (split_rect.x + 12, split_rect.y + 6))
            else:
                pygame.draw.rect(screen, PANEL_BORDER, split_rect, 1)

            self._row_hitboxes.append({"row": row_rect, "split": split_rect})

        self._create_buttons()
        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")
