from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

import pygame

from .base_dialog import BaseDialog, BUTTON_BG, BUTTON_SELECTED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED


GREEN = (80, 200, 120)
RED = (220, 80, 80)
SILVER = (190, 190, 190)
GOLD = (212, 175, 55)


class DiceRollDialog(BaseDialog):
    def __init__(self, screen_width: int, screen_height: int):
        super().__init__(screen_width, screen_height, width=720, height=420, draggable=True, center=True)
        self.game = None
        self.player = None
        self.decision_request = None
        self.roll_id: Optional[int] = None
        self.on_resolve: Optional[Callable[[str, Dict], None]] = None
        self._interactive: bool = False

        self._dice_images: Dict[int, pygame.Surface] = {}
        self._die_rects: Dict[str, pygame.Rect] = {}
        self._selected_die_ids: List[str] = []
        self._active_action_id: Optional[str] = None
        self._option_map: Dict[str, str] = {}
        self._action_map: Dict[str, dict] = {}

    def _sync_option_map_from_request(self) -> None:
        if self.decision_request is None:
            return
        for opt in list(getattr(self.decision_request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            action_id = str(payload.get("action_id", "") or "")
            if not action_id:
                continue
            self._option_map[action_id] = opt.option_id

    def _load_die_image(self, value: int, size: int) -> Optional[pygame.Surface]:
        if value in self._dice_images:
            return self._dice_images[value]
        try:
            img_path = Path("RuleSets") / "Dice" / f"{int(value)}.png"
            if not img_path.exists():
                return None
            img = pygame.image.load(str(img_path)).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, (size, size))
            self._dice_images[value] = img
            return img
        except Exception:
            return None

    def show(self, *, game, player, decision_request, on_resolve: Callable[[str, Dict], None]):
        self.game = game
        self.player = player
        self.decision_request = decision_request
        self.on_resolve = on_resolve
        self._interactive = bool(on_resolve)
        self._selected_die_ids = []
        self._active_action_id = None
        self._option_map = {}
        self._action_map = {}
        self.roll_id = None
        if decision_request is not None:
            ctx = dict(getattr(decision_request, "context", {}) or {})
            if "roll_id" in ctx:
                try:
                    self.roll_id = int(ctx.get("roll_id"))
                except Exception:
                    self.roll_id = None
        self._sync_option_map_from_request()
        super().show(callback=None)

    def hide(self):
        super().hide()
        self.game = None
        self.player = None
        self.decision_request = None
        self.on_resolve = None
        self._interactive = False
        self._selected_die_ids = []
        self._active_action_id = None
        self._option_map = {}
        self._action_map = {}
        self._die_rects = {}
        self.roll_id = None

    def _roll_state(self):
        if self.game is None or self.roll_id is None:
            return None
        mgr = getattr(self.game, "roll_manager", None)
        if mgr is None:
            return None
        return mgr.get_roll(self.roll_id)

    def _build_action_maps(self, state):
        self._option_map = {}
        self._action_map = {}
        self._sync_option_map_from_request()
        for action in list(getattr(state, "reroll_options", []) or []):
            action_id = str(action.get("action_id", "") or "")
            if not action_id:
                continue
            self._action_map[action_id] = dict(action)

    def _resolve_action(self, action_id: str, selected: Optional[List[str]] = None) -> bool:
        if not self.decision_request or not self.on_resolve or not self._interactive:
            return False
        self._sync_option_map_from_request()
        option_id = self._option_map.get(action_id)
        if not option_id:
            return False
        payload = {}
        if selected is not None:
            payload["selected_die_ids"] = list(selected)
        self.on_resolve(option_id, payload)
        self._selected_die_ids = []
        self._active_action_id = None
        return True

    def _handle_button_click(self, button_name: str) -> bool:
        if button_name in ("close", "cancel"):
            self.hide()
            return True
        if not self._interactive:
            return False
        if button_name == "make_roll":
            self._resolve_action("roll", [])
            # Keep dialog visible so the roll result and any follow-up reroll
            # decision can be displayed in-place.
            return True
        if button_name == "no_reroll":
            before_id = str(getattr(self.decision_request, "decision_id", "") or "")
            resolved = self._resolve_action("none", [])
            after_id = str(getattr(self.decision_request, "decision_id", "") or "")
            if resolved and after_id == before_id:
                self.hide()
            return True
        if button_name == "confirm_reroll":
            if not self._active_action_id:
                return True
            before_id = str(getattr(self.decision_request, "decision_id", "") or "")
            resolved = self._resolve_action(self._active_action_id, list(self._selected_die_ids))
            after_id = str(getattr(self.decision_request, "decision_id", "") or "")
            # If resolve triggers a follow-up reroll request synchronously, show() replaces
            # decision_request. Do not hide in that case.
            if resolved and after_id == before_id:
                self.hide()
            return True
        # Action buttons map directly to reroll actions
        if button_name.startswith("action:"):
            action_id = button_name.split(":", 1)[1]
            action = self._action_map.get(action_id)
            if action is None:
                return True
            mode = str(action.get("mode", "") or "")
            eligible = list(action.get("eligible_die_ids", []) or [])
            auto_all = bool(action.get("auto_select_all", False))
            if mode in ("all", "whole") or (mode in ("values", "ones", "any") and auto_all):
                before_id = str(getattr(self.decision_request, "decision_id", "") or "")
                resolved = self._resolve_action(action_id, eligible)
                after_id = str(getattr(self.decision_request, "decision_id", "") or "")
                if resolved and after_id == before_id:
                    self.hide()
                return True
            # Selection-based
            self._active_action_id = action_id
            self._selected_die_ids = []
            return True
        if button_name == "command_reroll":
            action = self._action_map.get("command_reroll")
            if action is None:
                return True
            mode = str(action.get("mode", "") or "")
            eligible = list(action.get("eligible_die_ids", []) or [])
            if mode in ("all", "whole"):
                before_id = str(getattr(self.decision_request, "decision_id", "") or "")
                resolved = self._resolve_action("command_reroll", eligible)
                after_id = str(getattr(self.decision_request, "decision_id", "") or "")
                if resolved and after_id == before_id:
                    self.hide()
                return True
            self._active_action_id = "command_reroll"
            self._selected_die_ids = []
            return True
        return False

    def _handle_dialog_click(self, mouse_pos) -> bool:
        if not self.visible:
            return False
        if not self._active_action_id or not self._interactive:
            return False
        action = self._action_map.get(self._active_action_id)
        if action is None:
            return False
        eligible = set(action.get("eligible_die_ids", []) or [])
        max_select = action.get("max_select")
        for die_id, rect in list(self._die_rects.items()):
            if rect.collidepoint(mouse_pos):
                if die_id not in eligible:
                    return True
                if die_id in self._selected_die_ids:
                    self._selected_die_ids.remove(die_id)
                else:
                    if max_select is not None and len(self._selected_die_ids) >= int(max_select):
                        return True
                    self._selected_die_ids.append(die_id)
                return True
        return False

    def _draw_check(self, screen: pygame.Surface, x: int, y: int, ok: bool):
        color = GREEN if ok else RED
        if ok:
            pygame.draw.line(screen, color, (x, y + 6), (x + 5, y + 12), 3)
            pygame.draw.line(screen, color, (x + 5, y + 12), (x + 14, y - 2), 3)
        else:
            pygame.draw.line(screen, color, (x, y), (x + 12, y + 12), 3)
            pygame.draw.line(screen, color, (x + 12, y), (x, y + 12), 3)

    @staticmethod
    def _comparison_text(op: str, target: int) -> str:
        normalized = str(op or "gte").strip().lower()
        if normalized == "gte":
            return f">= {int(target)}"
        if normalized == "gt":
            return f"> {int(target)}"
        if normalized == "lte":
            return f"<= {int(target)}"
        if normalized == "lt":
            return f"< {int(target)}"
        if normalized == "ne":
            return f"!= {int(target)}"
        return f"= {int(target)}"

    @staticmethod
    def _flatten_text_list(value) -> List[str]:
        out: List[str] = []
        for item in list(value or []):
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out

    @staticmethod
    def _get_roll_explanation(spec: Dict) -> Dict:
        value = spec.get("roll_explanation", None)
        if isinstance(value, dict):
            return dict(value)
        return {}

    @staticmethod
    def _contributor_type_label(value: str) -> str:
        key = str(value or "").strip().lower()
        labels = {
            "detachment_ability": "Detachment ability",
            "faction_rule": "Faction rule",
            "unit_ability": "Unit ability",
            "enhancement": "Enhancement",
            "stratagem": "Stratagem",
            "aura": "Aura",
            "core_rule": "Core rule",
            "rule": "Rule",
        }
        return labels.get(key, "Rule")

    @classmethod
    def _format_contributor_text(cls, contributor: Dict) -> str:
        source = str(contributor.get("source", "") or "").strip()
        reason = str(contributor.get("reason", "") or "").strip()
        value = contributor.get("value", None)
        ctype = cls._contributor_type_label(str(contributor.get("contributor_type", "") or "rule"))

        body = reason or source
        if source and reason and source.lower() not in reason.lower():
            body = f"{source}: {reason}"
        if not body:
            body = source or "modifier"

        has_value = False
        if value is not None:
            try:
                value_int = int(value)
                has_value = True
            except Exception:
                has_value = False
                value_int = 0
            if has_value and f"{value_int:+d}" not in body:
                body = f"{body} ({value_int:+d})"

        range_in = contributor.get("aura_range_inches", None)
        distance_in = contributor.get("aura_distance_inches", None)
        details = []
        if range_in is not None:
            try:
                details.append(f"range {float(range_in):.1f}\"")
            except Exception:
                details.append(f"range {range_in}\"")
        if distance_in is not None:
            try:
                details.append(f"distance {float(distance_in):.1f}\"")
            except Exception:
                details.append(f"distance {distance_in}\"")
        if details:
            body = f"{body} ({', '.join(details)})"
        return f"{ctype}: {body}"

    @classmethod
    def _format_condition_text(cls, spec: Dict) -> str:
        explanation = cls._get_roll_explanation(spec)
        condition = explanation.get("condition", {}) if isinstance(explanation, dict) and explanation.get("schema_version") == 1 else {}
        if isinstance(condition, dict):
            target = condition.get("target", None)
            op = str(condition.get("op", "") or "").strip().lower()
            applies_to = str(condition.get("applies_to", "") or "").strip().lower()
            if target is not None and op:
                try:
                    cmp = cls._comparison_text(op, int(target))
                except Exception:
                    cmp = ""
                if cmp:
                    label = str(condition.get("label", "") or "").strip()
                    if not label:
                        label = "Pass condition" if applies_to == "modified_sum" else "Success condition"
                    if applies_to == "modified_sum":
                        return f"{label}: modified sum {cmp}"
                    context = str(condition.get("context", "") or "").strip()
                    if context:
                        return f"{label}: each die {cmp} ({context})"
                    return f"{label}: each die {cmp}"

        sum_target = spec.get("sum_target", None)
        if sum_target is not None:
            try:
                cmp = cls._comparison_text(str(spec.get("sum_op", "gte") or "gte"), int(sum_target))
            except Exception:
                return ""
            return f"Pass condition: modified sum {cmp}"

        target = spec.get("target", None)
        if target is None:
            return ""
        try:
            cmp = cls._comparison_text(str(spec.get("target_op", "gte") or "gte"), int(target))
        except Exception:
            return ""
        context = str(spec.get("target_context", "") or "").strip()
        if context:
            return f"Success condition: each die {cmp} ({context})"
        return f"Success condition: each die {cmp}"

    @classmethod
    def _format_modifier_text(cls, spec: Dict, state) -> str:
        explanation = cls._get_roll_explanation(spec)
        if isinstance(explanation, dict) and explanation.get("schema_version") == 1:
            sum_mod = explanation.get("sum_modifier", {})
            if isinstance(sum_mod, dict):
                contributors = [dict(c) for c in list(sum_mod.get("contributors", []) or []) if isinstance(c, dict)]
                total = 0
                has_total = False
                try:
                    total = int(sum_mod.get("total", 0) or 0)
                    has_total = True
                except Exception:
                    total = 0
                    has_total = False
                if contributors or has_total or spec.get("sum_target", None) is not None or bool(spec.get("show_sum", False)):
                    if has_total:
                        raw_total = int(getattr(state, "total", 0) or 0)
                        final_total = raw_total + total
                        detail = f"Modifiers: {total:+d} (raw {raw_total} -> {final_total})"
                    else:
                        detail = "Modifiers: unspecified"
                    formatted: List[str] = []
                    for item in contributors:
                        text = cls._format_contributor_text(item)
                        if text:
                            formatted.append(text)
                    if formatted:
                        detail = f"{detail}; {'; '.join(formatted)}"
                    if has_total and total == 0 and not formatted:
                        return "Modifiers: none"
                    return detail

            target_mod = explanation.get("target_modifier", {})
            if isinstance(target_mod, dict):
                contributors = [dict(c) for c in list(target_mod.get("contributors", []) or []) if isinstance(c, dict)]
                target = target_mod.get("final_target", spec.get("target", None))
                base_target = target_mod.get("base_target", spec.get("target_base", None))
                parts: List[str] = []
                try:
                    if target is not None and base_target is not None:
                        target_val = int(target)
                        base_val = int(base_target)
                        if target_val != base_val:
                            parts.append(f"base {base_val}+ -> {target_val}+ ({target_val - base_val:+d})")
                except Exception:
                    pass
                for item in contributors:
                    text = cls._format_contributor_text(item)
                    if text:
                        parts.append(text)
                if parts:
                    return f"Modifiers: {'; '.join(parts)}"
                if target is not None:
                    return "Modifiers: none"

        sum_target = spec.get("sum_target", None)
        if sum_target is not None:
            try:
                mod = int(spec.get("sum_modifier", 0) or 0)
            except Exception:
                mod = 0
            reasons = cls._flatten_text_list(spec.get("sum_modifier_reasons", []))
            if mod == 0 and not reasons:
                return "Modifiers: none"
            raw_total = int(getattr(state, "total", 0) or 0)
            final_total = raw_total + mod
            detail = f"Modifiers: {mod:+d} (raw {raw_total} -> {final_total})"
            if reasons:
                detail = f"{detail}; {'; '.join(reasons)}"
            return detail

        reasons = cls._flatten_text_list(spec.get("target_modifier_reasons", []))
        target = spec.get("target", None)
        base_target = spec.get("target_base", None)
        parts: List[str] = []
        try:
            if target is not None and base_target is not None:
                target_val = int(target)
                base_val = int(base_target)
                if target_val != base_val:
                    parts.append(f"base {base_val}+ -> {target_val}+ ({target_val - base_val:+d})")
        except Exception:
            pass
        parts.extend(reasons)
        if not parts:
            return "Modifiers: none"
        return f"Modifiers: {'; '.join(parts)}"

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        # Reset buttons each draw to keep positions in sync
        self.buttons.clear()
        self.button_states.clear()
        self.draw_dialog_background(screen)
        title = "Dice Roll"
        self.draw_title_bar(screen, title)

        state = self._roll_state()
        if state is None:
            self.draw_text_wrapped(
                screen,
                "No roll data available.",
                self.x + 20,
                self.y + self.title_bar_height + 20,
                self.width - 40,
                self.font_small,
                TEXT_SECONDARY,
            )
            self.add_button("close", self.width - 90, self.height - 50, 70, 30, enabled=True)
            self.draw_button(screen, "close", "Close", text_color=TEXT_PRIMARY)
            return

        spec = dict(getattr(state, "spec", {}) or {})
        reason = str(spec.get("reason", "") or "Roll")
        roll_type = str(spec.get("roll_type", "") or "")
        display_kind = str(spec.get("display_kind", "") or "")

        y = self.y + self.title_bar_height + 10
        self.draw_text_wrapped(
            screen,
            reason,
            self.x + 20,
            y,
            self.width - 40,
            self.font_medium,
            TEXT_PRIMARY,
            line_height=20,
        )
        y += 30
        if roll_type:
            rt_surface = self.font_small.render(f"Type: {roll_type}", True, TEXT_SECONDARY)
            screen.blit(rt_surface, (self.x + 20, y))
            y += 18

        if state.status != "rolled":
            if self._interactive:
                self.add_button("make_roll", 20, self.height - 55, 140, 35, enabled=True)
                self.draw_button(screen, "make_roll", "Make Roll", text_color=TEXT_PRIMARY)
            else:
                self.draw_text_wrapped(
                    screen,
                    "Waiting for roll...",
                    self.x + 20,
                    self.height - 55,
                    self.width - 40,
                    self.font_small,
                    TEXT_SECONDARY,
                )
                self.add_button("close", self.width - 90, self.height - 55, 70, 30, enabled=True)
                self.draw_button(screen, "close", "Close", text_color=TEXT_PRIMARY)
            return

        # Build action maps for rerolls
        self._build_action_maps(state)

        dice = list(getattr(state, "dice", []) or [])
        sorted_ids = list(getattr(state, "sorted_ids", []) or [])
        dice_by_id = {str(d.get("die_id", "")): d for d in dice}
        ordered = list(dice)
        if display_kind != "d33":
            ordered = [dice_by_id.get(did) for did in sorted_ids if did in dice_by_id]
            if not ordered:
                ordered = dice

        die_size = 48
        start_x = self.x + 20
        dy = y + 10
        gap = 10
        self._die_rects = {}
        for idx, die in enumerate(ordered):
            if die is None:
                continue
            val = int(die.get("value", 0) or 0)
            die_id = str(die.get("die_id", ""))
            img = self._load_die_image(val, die_size)
            rect = pygame.Rect(start_x + idx * (die_size + gap), dy, die_size, die_size)
            self._die_rects[die_id] = rect
            # Background and border
            pygame.draw.rect(screen, BUTTON_BG, rect)
            border_color = TEXT_SECONDARY
            succ = getattr(state, "per_die_success", {}).get(die_id)
            if succ is True:
                border_color = GREEN
            elif succ is False:
                border_color = RED
            if bool(die.get("is_derived", False)):
                border_color = SILVER
            crit_threshold = spec.get("crit_threshold", None)
            if crit_threshold is not None and not bool(die.get("is_derived", False)):
                try:
                    if int(val) >= int(crit_threshold):
                        border_color = GOLD
                except Exception:
                    pass
            pygame.draw.rect(screen, border_color, rect, 2)
            if img is not None:
                screen.blit(img, rect.topleft)
            else:
                txt = self.font_medium.render(str(val), True, TEXT_PRIMARY)
                screen.blit(txt, txt.get_rect(center=rect.center))
            if die_id in self._selected_die_ids:
                pygame.draw.rect(screen, BUTTON_SELECTED, rect, 3)

        # Sum display
        sum_target = spec.get("sum_target", None)
        show_sum = bool(spec.get("show_sum", False)) or sum_target is not None
        if show_sum:
            total = int(getattr(state, "total", 0) or 0)
            try:
                mod = int(spec.get("sum_modifier", 0) or 0)
            except Exception:
                mod = 0
            total_display = total + mod
            op = str(spec.get("sum_op", "gte") or "gte").strip().lower()
            target_text = ""
            if sum_target is not None:
                if op == "gte":
                    target_text = f"{sum_target}+"
                elif op == "gt":
                    target_text = f">{sum_target}"
                elif op == "lte":
                    target_text = f"<={sum_target}"
                elif op == "lt":
                    target_text = f"<{sum_target}"
                elif op == "ne":
                    target_text = f"!={sum_target}"
                else:
                    target_text = f"{sum_target}"
            sum_label = "SUM"
            if display_kind == "d33":
                sum_label = "D33"
            sum_text = f"{sum_label} {total_display}"
            if mod:
                sum_text = f"{sum_text} (raw {total} {mod:+d})"
            if target_text:
                sum_text = f"{sum_text} vs {target_text}"
            sum_surface = self.font_medium.render(sum_text, True, TEXT_PRIMARY)
            sum_x = self.x + 20
            sum_y = dy + die_size + 12
            screen.blit(sum_surface, (sum_x, sum_y))
            if sum_target is not None:
                ok = bool(getattr(state, "sum_success", False))
                self._draw_check(screen, sum_x + sum_surface.get_width() + 10, sum_y + 4, ok)
            y = sum_y + 24
        else:
            y = dy + die_size + 20

        # D33 combined label (two D3 dice)
        if display_kind == "d33" and len(ordered) >= 2:
            try:
                d1 = int(ordered[0].get("value", 0) or 0)
                d2 = int(ordered[1].get("value", 0) or 0)
                label = f"{d1}{d2}"
            except Exception:
                label = ""
            if label:
                tag = self.font_small.render(f"Combined: {label}", True, TEXT_SECONDARY)
                screen.blit(tag, (self.x + 20, y))
                y += 18

        condition_text = self._format_condition_text(spec)
        if condition_text:
            y = self.draw_text_wrapped(
                screen,
                condition_text,
                self.x + 20,
                y + 2,
                self.width - 40,
                self.font_small,
                TEXT_SECONDARY,
            )
        modifier_text = self._format_modifier_text(spec, state)
        if modifier_text:
            y = self.draw_text_wrapped(
                screen,
                modifier_text,
                self.x + 20,
                y + 2,
                self.width - 40,
                self.font_small,
                TEXT_SECONDARY,
            )

        # Legend for derived/crit
        legend_x = self.x + 20
        legend_y = y + 5
        legend_items = []
        derived_kinds = []
        for d in dice:
            if not bool(d.get("is_derived", False)):
                continue
            kind = str(d.get("derived_kind", "") or "").strip()
            if kind:
                derived_kinds.append(kind)
        if any(bool(d.get("is_derived", False)) for d in dice):
            legend_items.append(("Derived die", SILVER))
        for kind in sorted(set(derived_kinds)):
            legend_items.append((f"Derived: {kind}", SILVER))
        crit_thresh = spec.get("crit_threshold", None)
        if crit_thresh is not None:
            crit_label = "Crit"
            if roll_type == "wound":
                crit_label = "Crit Wound"
            elif roll_type == "hit":
                crit_label = "Crit Hit"
            legend_items.append((f"{crit_label} {crit_thresh}+", GOLD))
        if legend_items:
            lx = legend_x
            for label, color in legend_items:
                box = pygame.Rect(lx, legend_y, 14, 14)
                pygame.draw.rect(screen, color, box, 2)
                txt = self.font_small.render(label, True, TEXT_SECONDARY)
                screen.blit(txt, (lx + 20, legend_y - 1))
                lx += 20 + txt.get_width() + 20
            y = legend_y + 22

        # Reroll options
        actions = []
        if self._interactive:
            actions = [a for a in list(getattr(state, "reroll_options", []) or []) if a.get("action_id") not in ("none", "command_reroll")]
        if actions:
            self.draw_text_wrapped(
                screen,
                "Re-roll options:",
                self.x + 20,
                y,
                self.width - 40,
                self.font_small,
                TEXT_SECONDARY,
            )
            y += 18

        bottom_row_y = self.height - 55
        keep_button_x = 20
        keep_button_w = 120
        right_button_w = 170
        right_button_x = self.width - right_button_w - 20

        # Ability/rule re-roll actions align on the same bottom row as Keep.
        if actions and self._interactive:
            bx = keep_button_x + keep_button_w + 8
            right_limit = right_button_x - 8
            for action in actions:
                label = str(action.get("label", "") or "Re-roll")
                action_id = str(action.get("action_id", "") or "")
                bw = max(110, min(180, 12 + self.font_small.size(label)[0]))
                if bx + bw > right_limit:
                    break
                self.add_button(f"action:{action_id}", bx, bottom_row_y, bw, 35, enabled=True)
                self.draw_button(screen, f"action:{action_id}", label, text_color=TEXT_PRIMARY)
                bx += bw + 8

        # Reroll selection confirm
        if self._active_action_id and self._interactive:
            self.add_button("confirm_reroll", right_button_x, bottom_row_y, right_button_w, 35, enabled=bool(self._selected_die_ids))
            self.draw_button(screen, "confirm_reroll", "Re-roll selected", text_color=TEXT_PRIMARY)
        else:
            # Command Re-roll button (aligned with bottom action row).
            cmd_action = self._action_map.get("command_reroll") if self._interactive else None
            cmd_enabled = cmd_action is not None
            cmd_color = TEXT_PRIMARY if cmd_enabled else TEXT_DISABLED
            self.add_button("command_reroll", right_button_x, bottom_row_y, right_button_w, 35, enabled=bool(cmd_enabled))
            self.draw_button(screen, "command_reroll", "Command Re-roll", text_color=cmd_color)

        # No re-roll / Close
        if self._interactive:
            self.add_button("no_reroll", keep_button_x, bottom_row_y, keep_button_w, 35, enabled=True)
            self.draw_button(screen, "no_reroll", "Keep", text_color=TEXT_PRIMARY)
        else:
            self.add_button("close", 20, self.height - 55, 90, 35, enabled=True)
            self.draw_button(screen, "close", "Close", text_color=TEXT_PRIMARY)
