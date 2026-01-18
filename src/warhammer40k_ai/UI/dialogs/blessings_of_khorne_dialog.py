import pygame
from typing import Optional, Callable, List, Dict, Any

from .base_dialog import BaseDialog, BUTTON_SELECTED, BUTTON_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_ERROR


class BlessingsOfKhorneDialog(BaseDialog):
    """
    Human UI for:
    - viewing Blessings dice
    - optionally re-rolling up to two dice (Favoured of Khorne)
    - selecting blessings to activate (or Reborn in Blood at start-of-round)
    """

    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=640, height=520, draggable=True)
        self.player = None
        self.game = None
        self.army = None
        self.manager = None
        self.ctx = None
        self.on_confirm: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.apply_choice: bool = True

        self._selected_reroll: List[int] = []
        self._reroll_done: bool = False
        self._selected_blessings: List[str] = []
        self._use_reborn: bool = False
        self._error_text: str = ""

        # Hitboxes
        self._die_rects: List[pygame.Rect] = []
        self._blessing_rects: List[tuple[str, pygame.Rect]] = []
        self._reborn_rect: Optional[pygame.Rect] = None

    def show(self, *, player, game, army, ctx, on_confirm: Callable[[Dict[str, Any]], None], apply_choice: bool = True, on_cancel: Optional[Callable[[], None]] = None) -> None:
        super().show(callback=None)
        self.player = player
        self.game = game
        self.army = army
        self.manager = getattr(army, "blessings_of_khorne", None)
        self.ctx = ctx
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.apply_choice = bool(apply_choice)

        self._selected_reroll = []
        self._reroll_done = False
        self._selected_blessings = []
        self._use_reborn = False
        self._error_text = ""

    def hide(self):
        super().hide()
        self.player = None
        self.game = None
        self.army = None
        self.manager = None
        self.ctx = None
        self.on_confirm = None
        self.on_cancel = None
        self._die_rects = []
        self._blessing_rects = []
        self._reborn_rect = None

    # --- Events ---
    def _handle_button_click(self, button_name: str) -> bool:
        if button_name in ("cancel", "close"):
            self.hide()
            try:
                if callable(self.on_cancel):
                    self.on_cancel()
            except Exception:
                pass
            return True

        if button_name == "reroll":
            if self._reroll_done:
                return True
            if not self.manager or not self.ctx:
                return True
            try:
                self.manager.reroll_indices(self.ctx, list(self._selected_reroll))
                self._reroll_done = True
                self._selected_reroll = []
                self._error_text = ""
            except Exception as e:
                self._error_text = str(e)
            return True

        if button_name == "confirm":
            if not self.manager or not self.ctx:
                return True
            # Validate selection before applying
            preview = self.manager.preview_choice(
                self.ctx,
                selected_blessing_keys=list(self._selected_blessings),
                use_reborn_in_blood=bool(self._use_reborn),
            )
            if not preview.get("ok", False):
                self._error_text = preview.get("error", "Invalid selection")
                return True

            if self.apply_choice:
                try:
                    res = self.manager.apply_choice(
                        self.ctx,
                        selected_blessing_keys=list(self._selected_blessings),
                        use_reborn_in_blood=bool(self._use_reborn),
                    )
                except Exception as e:
                    self._error_text = str(e)
                    return True
            else:
                res = {
                    "activated": list(self._selected_blessings),
                    "spent_indices": list(preview.get("spent_indices", [])),
                    "reborn_used": bool(self._use_reborn),
                    "allocation": preview.get("allocation", {}),
                }

            payload = {
                "player": self.player,
                "ctx": self.ctx,
                "result": res,
                "selected_blessings": list(self._selected_blessings),
                "use_reborn": bool(self._use_reborn),
            }
            if callable(self.on_confirm):
                self.on_confirm(payload)
            self.hide()
            return True

        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        if not self.ctx:
            return False

        # Dice selection for rerolls
        for idx, r in enumerate(self._die_rects):
            if r.collidepoint(mouse_pos):
                if self._reroll_done:
                    return True
                if int(getattr(self.ctx, "rerolls_allowed", 0) or 0) <= 0:
                    return True
                if idx in self._selected_reroll:
                    self._selected_reroll.remove(idx)
                else:
                    if len(self._selected_reroll) < int(self.ctx.rerolls_allowed):
                        self._selected_reroll.append(idx)
                self._error_text = ""
                return True

        # Reborn toggle
        if self._reborn_rect and self._reborn_rect.collidepoint(mouse_pos):
            if self._can_use_reborn():
                self._use_reborn = not self._use_reborn
                if self._use_reborn:
                    self._selected_blessings = []
            self._error_text = ""
            return True

        # Blessings selection
        for key, r in self._blessing_rects:
            if r.collidepoint(mouse_pos):
                if self._use_reborn:
                    return True
                if key in self._selected_blessings:
                    self._selected_blessings.remove(key)
                else:
                    max_act = int(getattr(self.ctx, "max_activations", 0) or 0)
                    if len(self._selected_blessings) < max_act:
                        self._selected_blessings.append(key)
                self._error_text = ""
                return True

        return False

    # --- Drawing ---
    def _can_use_reborn(self) -> bool:
        if not self.ctx:
            return False
        if not bool(getattr(self.ctx, "reborn_in_blood_available", False)):
            return False
        # Need triple 6 present
        dice = list(getattr(self.ctx, "dice", []) or [])
        return sum(1 for d in dice if int(d) == 6) >= 3

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self.draw_dialog_background(screen)
        title = "Blessings of Khorne"
        subtitle = f"{getattr(self.player, 'name', 'Player')} - Battle Round {getattr(getattr(self.game, 'turn', None), '__str__', lambda: '?')()}"
        self.draw_title_bar(screen, title, subtitle)

        if not self.ctx or not self.manager:
            self.draw_text_centered(screen, "No context available", y_offset=120, color=TEXT_ERROR)
            return

        # Dice row
        dice = list(getattr(self.ctx, "dice", []) or [])
        dice_y = self.y + 80
        dice_x = self.x + 20
        die_w = 44
        die_h = 44
        gap = 8
        self._die_rects = []
        for i, v in enumerate(dice):
            x = dice_x + i * (die_w + gap)
            r = pygame.Rect(x, dice_y, die_w, die_h)
            self._die_rects.append(r)
            sel = (i in self._selected_reroll)
            bg = BUTTON_SELECTED if sel else BUTTON_BG
            pygame.draw.rect(screen, bg, r)
            pygame.draw.rect(screen, (90, 90, 100), r, 1)
            txt = self.font_medium.render(str(int(v)), True, TEXT_PRIMARY)
            screen.blit(txt, txt.get_rect(center=r.center))

        # Reroll hint
        rr_allowed = int(getattr(self.ctx, "rerolls_allowed", 0) or 0)
        rr_text = "No rerolls" if rr_allowed <= 0 else f"Reroll up to {rr_allowed} dice (click dice to select)"
        if self._reroll_done:
            rr_text = "Rerolls used"
        rr_surface = self.font_small.render(rr_text, True, TEXT_SECONDARY)
        screen.blit(rr_surface, (self.x + 20, dice_y + die_h + 10))

        # Reborn checkbox (if available)
        self._reborn_rect = None
        reborn_y = dice_y + die_h + 40
        if bool(getattr(self.ctx, "reborn_in_blood_available", False)):
            can = self._can_use_reborn()
            label = "Use Reborn in Blood (triple 6) instead of start-of-round Blessings"
            box = pygame.Rect(self.x + 20, reborn_y, 18, 18)
            self._reborn_rect = pygame.Rect(self.x + 20, reborn_y, self.width - 40, 22)
            pygame.draw.rect(screen, (60, 60, 67), box)
            if self._use_reborn:
                pygame.draw.rect(screen, (100, 255, 100), box.inflate(-6, -6))
            color = TEXT_PRIMARY if can else (120, 120, 120)
            t = self.font_small.render(label, True, color)
            screen.blit(t, (box.right + 10, reborn_y - 2))

        # Blessings list
        list_y = reborn_y + (34 if self._reborn_rect is not None else 10)
        list_title = self.font_medium.render("Select Blessings to activate:", True, TEXT_PRIMARY)
        screen.blit(list_title, (self.x + 20, list_y))

        self._blessing_rects = []
        keys = list(self.manager.definitions.keys())
        # Stable order based on DEFAULT_BLESSINGS insertion order
        row_y = list_y + 30
        row_h = 28
        for i, key in enumerate(keys):
            d = self.manager.definitions[key]
            disabled = bool(key in getattr(self.ctx, "already_active_keys", set()))
            r = pygame.Rect(self.x + 20, row_y + i * row_h, self.width - 40, row_h - 4)
            self._blessing_rects.append((key, r))
            is_sel = key in self._selected_blessings
            bg = (55, 55, 60)
            if is_sel:
                bg = BUTTON_SELECTED
            if disabled:
                bg = (40, 40, 40)
            pygame.draw.rect(screen, bg, r)
            pygame.draw.rect(screen, (75, 75, 82), r, 1)
            name = f"{d.name} - {d.short_effect}"
            color = TEXT_SECONDARY if disabled else TEXT_PRIMARY
            screen.blit(self.font_small.render(name, True, color), (r.x + 8, r.y + 6))

        # Error / preview
        preview = self.manager.preview_choice(
            self.ctx,
            selected_blessing_keys=list(self._selected_blessings),
            use_reborn_in_blood=bool(self._use_reborn),
        )
        preview_y = self.y + self.height - 120
        if self._error_text:
            screen.blit(self.font_small.render(self._error_text, True, TEXT_ERROR), (self.x + 20, preview_y))
        elif not preview.get("ok", True):
            screen.blit(self.font_small.render(preview.get("error", "Invalid"), True, TEXT_ERROR), (self.x + 20, preview_y))
        else:
            spent = preview.get("spent_indices", [])
            msg = "Valid selection"
            if spent:
                msg = f"Valid - spends dice: {', '.join(str(i+1) for i in spent)}"
            screen.blit(self.font_small.render(msg, True, TEXT_SECONDARY), (self.x + 20, preview_y))

            # Per-blessing spend breakdown (UX)
            alloc = preview.get("allocation") or {}
            line_y = preview_y + 18
            try:
                dice_vals = list(getattr(self.ctx, "dice", []) or [])
            except Exception:
                dice_vals = []
            # Show selected blessings first, in selection order
            if self._use_reborn and "REBORN_IN_BLOOD" in alloc:
                idxs = list(alloc.get("REBORN_IN_BLOOD") or [])
                vals = [str(int(dice_vals[i])) for i in idxs if 0 <= i < len(dice_vals)]
                detail = f"Reborn in Blood: spends dice #{', '.join(str(i+1) for i in idxs)} ({', '.join(vals)})"
                screen.blit(self.font_small.render(detail, True, TEXT_SECONDARY), (self.x + 20, line_y))
            else:
                for key in list(self._selected_blessings):
                    if key not in alloc:
                        continue
                    idxs = list(alloc.get(key) or [])
                    vals = [str(int(dice_vals[i])) for i in idxs if 0 <= i < len(dice_vals)]
                    try:
                        name = self.manager.definitions[key].name
                    except Exception:
                        name = str(key)
                    detail = f"{name}: spends dice #{', '.join(str(i+1) for i in idxs)} ({', '.join(vals)})"
                    screen.blit(self.font_small.render(detail, True, TEXT_SECONDARY), (self.x + 20, line_y))
                    line_y += 18

        # Buttons
        can_reroll = (rr_allowed > 0) and (not self._reroll_done) and (len(self._selected_reroll) > 0)
        self.add_button("reroll", 20, self.height - 55, 140, 35, enabled=can_reroll)
        self.add_button("confirm", self.width - 260, self.height - 55, 120, 35, enabled=True)
        self.add_button("cancel", self.width - 130, self.height - 55, 110, 35, enabled=True)
        self.draw_button(screen, "reroll", "Re-roll")
        self.draw_button(screen, "confirm", "Confirm")
        self.draw_button(screen, "cancel", "Cancel")

