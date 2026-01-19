import pygame

from warhammer40k_ai.utility.event_bus import get_recent_actions, get_recent_dice

from ..ui_constants import TILE_SIZE


def draw_top_status_pane(self, pane_height_px: int) -> None:
    left = self.battlefield_left
    width = self.scaled_battlefield_width
    pygame.draw.rect(self.screen, (35, 35, 38), (left, 0, width, pane_height_px))
    pygame.draw.rect(self.screen, (63, 63, 70), (left, 0, width, pane_height_px), 2)
    # Clear stale mission/secondary hitboxes before rebuilding
    try:
        if hasattr(self, "_ui_hitboxes"):
            for key in list(self._ui_hitboxes.keys()):
                if key == "primary" or str(key).startswith("sec_") or str(key).startswith("vp_") or str(key).startswith("cp_"):
                    self._ui_hitboxes.pop(key, None)
    except Exception:
        pass

    third = width // 3
    p1_rect = pygame.Rect(left, 0, third, pane_height_px)
    mid_rect = pygame.Rect(left + third, 0, third, pane_height_px)
    p2_rect = pygame.Rect(left + 2 * third, 0, third, pane_height_px)

    try:
        font = pygame.font.SysFont('Arial', 16, bold=True)
        small = pygame.font.SysFont('Arial', 14)
        status_font = pygame.font.SysFont('Arial', 18, bold=True)
    except Exception:
        font = pygame.font.Font(None, 16)
        small = pygame.font.Font(None, 14)
        status_font = pygame.font.Font(None, 18)

    def draw_box(rect: pygame.Rect, text: str, align: str = 'left', bg=(60,60,67)):
        pygame.draw.rect(self.screen, bg, rect)
        pygame.draw.rect(self.screen, (90,90,100), rect, 1)
        ts = font.render(text, True, (255,255,255))
        tr = ts.get_rect()
        if align == 'left':
            tr.topleft = (rect.x + 8, rect.y + rect.height//2 - ts.get_height()//2)
        elif align == 'right':
            tr.topright = (rect.right - 8, rect.y + rect.height//2 - ts.get_height()//2)
        else:
            tr.center = rect.center
        self.screen.blit(ts, tr)

    p1 = self.player1
    p2 = self.player2

    box_w = p1_rect.width // 6 - 6
    x0 = p1_rect.x + 6
    y0 = p1_rect.y + 6
    h = pane_height_px - 12
    vp1_rect = pygame.Rect(x0, y0, box_w, h)
    draw_box(vp1_rect, f"VP: {p1.score}")
    cp1_rect = pygame.Rect(x0 + box_w + 6, y0, box_w, h)
    draw_box(cp1_rect, f"CP: {p1.command_points}")
    if not hasattr(self, "_ui_hitboxes"):
        self._ui_hitboxes = {}
    self._ui_hitboxes["vp_p1"] = (pygame.Rect(vp1_rect), p1)
    self._ui_hitboxes["cp_p1"] = (pygame.Rect(cp1_rect), p1)
    sec_area_width = int((p1_rect.width - (2 * (box_w + 6)) - 12) * 0.95)
    draw_secondaries_buttons(self, pygame.Rect(x0 + 2*(box_w + 6), y0, sec_area_width, h), p1, align='left')

    # Move primary button 1" (TILE_SIZE px) further left
    primary_rect = pygame.Rect(mid_rect.x + 6 - int(1 * TILE_SIZE), y0, int(mid_rect.width * 0.45 * 0.9), h)
    draw_primary_button(self, primary_rect)
    if self.game.is_in_setup_phase():
        round_text = self.game.get_current_setup_phase().name.replace('_', ' ').title()
    else:
        round_text = f"Turn {self.game.turn} - {self.game.get_current_player().name} - {self.game.phase.name.replace('_',' ').title()}"
    st = status_font.render(round_text, True, (255, 140, 0))
    info_rect = pygame.Rect(primary_rect.right + 10, y0, mid_rect.right - (primary_rect.right + 18), h)
    sr = st.get_rect(center=info_rect.center)
    self.screen.blit(st, sr)

    box_w2 = p2_rect.width // 6 - 6
    y2 = p2_rect.y + 6
    h2 = h
    vp2_rect = pygame.Rect(p2_rect.right - box_w2 - 6, y2, box_w2, h2)
    draw_box(vp2_rect, f"VP: {p2.score}", align='right')
    cp2_rect = pygame.Rect(p2_rect.right - 2*(box_w2 + 6), y2, box_w2, h2)
    draw_box(cp2_rect, f"CP: {p2.command_points}", align='right')
    if not hasattr(self, "_ui_hitboxes"):
        self._ui_hitboxes = {}
    self._ui_hitboxes["vp_p2"] = (pygame.Rect(vp2_rect), p2)
    self._ui_hitboxes["cp_p2"] = (pygame.Rect(cp2_rect), p2)
    sec2_area_width = int((p2_rect.width - (2 * (box_w2 + 6)) - 12) * 0.95)
    # Position Player 2 secondaries area immediately to the left of the CP/VP boxes
    sec2_x = p2_rect.right - 2*(box_w2 + 6) - 6 - sec2_area_width
    draw_secondaries_buttons(self, pygame.Rect(sec2_x, y2, sec2_area_width, h2), p2, align='right')

def draw_primary_button(self, rect: pygame.Rect) -> None:
    pygame.draw.rect(self.screen, (60,60,67), rect)
    pygame.draw.rect(self.screen, (90,90,100), rect, 1)
    card = getattr(self.game.get_current_player(), 'primary_mission', None)
    label = card.name if card else 'Primary: None'
    try:
        font = pygame.font.SysFont('Arial', 16, bold=True)
    except Exception:
        font = pygame.font.Font(None, 16)
    ts = font.render(label, True, (255,255,255))
    tr = ts.get_rect(center=rect.center)
    self.screen.blit(ts, tr)
    # register for click detection
    if not hasattr(self, '_ui_hitboxes'):
        self._ui_hitboxes = {}
    self._ui_hitboxes['primary'] = (pygame.Rect(rect), card)

def draw_secondaries_buttons(self, rect: pygame.Rect, player, align: str = 'left') -> None:
    pygame.draw.rect(self.screen, (50,50,55), rect)
    pygame.draw.rect(self.screen, (90,90,100), rect, 1)
    try:
        font = pygame.font.SysFont('Arial', 14, bold=False)
    except Exception:
        font = pygame.font.Font(None, 14)
    actives = getattr(player, 'active_secondaries', []) or []
    btn_w = (rect.width - 12) // 2
    for i in range(2):
        sub = pygame.Rect(rect.x + 4 + i * (btn_w + 4), rect.y + 4, btn_w, rect.height - 8)
        name = actives[i].name if i < len(actives) else 'None'
        bg = (80,80,90) if i < len(actives) else (70,70,75)
        pygame.draw.rect(self.screen, bg, sub)
        pygame.draw.rect(self.screen, (100,100,110), sub, 1)
        ts = font.render(name, True, (230,230,230))
        tr = ts.get_rect(center=sub.center)
        self.screen.blit(ts, tr)
        if not hasattr(self, '_ui_hitboxes'):
            self._ui_hitboxes = {}
        self._ui_hitboxes[f"sec_{id(sub)}"] = (pygame.Rect(sub), actives[i] if i < len(actives) else None)

def draw_bottom_logs_pane(self) -> None:
    height = self.scaled_info_height
    y = self.scaled_battlefield_height
    left = 0
    width = self.screen.get_width()
    pygame.draw.rect(self.screen, (45,45,48), (left, y, width, height))
    pygame.draw.rect(self.screen, (63,63,70), (left, y, width, height), 2)

    # Layout: Rules - P1 Actions - P1 Dice - P2 Dice - P2 Actions - Rules
    strat_w = max(120, int(width * 0.10))
    remaining = max(0, width - (strat_w * 2))
    box_w = remaining // 4

    x_cursor = left
    strat_left_rect = pygame.Rect(x_cursor, y, strat_w, height)
    x_cursor += strat_w
    boxes = [
        pygame.Rect(x_cursor + i * box_w, y, box_w, height) for i in range(4)
    ]
    x_cursor += box_w * 4
    strat_right_rect = pygame.Rect(x_cursor, y, width - x_cursor, height)  # Fill to end

    p1 = self.player1
    p2 = self.player2
    p1_name = p1.name
    p2_name = p2.name
    p1_actions = get_recent_actions(p1, limit=50)
    p1_dice = get_recent_dice(p1, limit=50)
    p2_actions = get_recent_actions(p2, limit=50)
    p2_dice = get_recent_dice(p2, limit=50)

    # Draw left/right rule buttons (stacked)
    half_h = max(1, height // 2)
    det_left_rect = pygame.Rect(strat_left_rect.x, strat_left_rect.y, strat_left_rect.width, half_h)
    army_left_rect = pygame.Rect(strat_left_rect.x, strat_left_rect.y + half_h, strat_left_rect.width, height - half_h)
    det_right_rect = pygame.Rect(strat_right_rect.x, strat_right_rect.y, strat_right_rect.width, half_h)
    army_right_rect = pygame.Rect(strat_right_rect.x, strat_right_rect.y + half_h, strat_right_rect.width, height - half_h)

    draw_rule_button(self, det_left_rect, "Detachment Rule", self.player1, "detachment")
    draw_rule_button(self, army_left_rect, "Army Rule", self.player1, "army")
    draw_rule_button(self, det_right_rect, "Detachment Rule", self.player2, "detachment")
    draw_rule_button(self, army_right_rect, "Army Rule", self.player2, "army")

    # Save hitboxes for click handling
    if not hasattr(self, '_ui_hitboxes'):
        self._ui_hitboxes = {}
    self._ui_hitboxes.pop('strat_p1', None)
    self._ui_hitboxes.pop('strat_p2', None)
    self._ui_hitboxes['det_rule_p1'] = (pygame.Rect(det_left_rect), self.player1)
    self._ui_hitboxes['army_rule_p1'] = (pygame.Rect(army_left_rect), self.player1)
    self._ui_hitboxes['det_rule_p2'] = (pygame.Rect(det_right_rect), self.player2)
    self._ui_hitboxes['army_rule_p2'] = (pygame.Rect(army_right_rect), self.player2)

    # Initialize bottom log scroll state and hitboxes
    if not isinstance(getattr(self, '_bottom_log_scroll', None), dict):
        self._bottom_log_scroll = {
            'p1_actions': 0,
            'p1_dice': 0,
            'p2_dice': 0,
            'p2_actions': 0,
        }
    self._bottom_log_boxes = {
        'p1_actions': boxes[0],
        'p1_dice': boxes[1],
        'p2_dice': boxes[2],
        'p2_actions': boxes[3],
    }

    # Draw the four log boxes with wrapping and scroll support
    draw_scroll_text_box(self, boxes[0], p1_actions, key='p1_actions', title=f"{p1_name} Actions")
    draw_scroll_text_box(self, boxes[1], p1_dice, key='p1_dice', title=f"{p1_name} Dice")
    draw_scroll_text_box(self, boxes[2], p2_dice, key='p2_dice', title=f"{p2_name} Dice")
    draw_scroll_text_box(self, boxes[3], p2_actions, key='p2_actions', title=f"{p2_name} Actions")

def draw_stratagem_panes(self) -> None:
    if not hasattr(self, '_ui_hitboxes'):
        self._ui_hitboxes = {}
    # Clear old stratagem item hitboxes
    for key in list(self._ui_hitboxes.keys()):
        if str(key).startswith("strat_item_"):
            self._ui_hitboxes.pop(key, None)

    panes = [
        ("p1", self.player1, self.left_stratagem_pane),
        ("p2", self.player2, self.right_stratagem_pane),
    ]
    for prefix, player, pane in panes:
        if pane is None or player is None:
            continue
        mgr = getattr(player, "stratagems", None)
        items = []
        try:
            if self.game is not None and hasattr(self.game, "is_in_setup_phase") and self.game.is_in_setup_phase():
                items = []
            elif mgr is not None:
                items = mgr.get_phase_stratagem_items() or []
        except Exception:
            items = []
        for item in items:
            try:
                item["owner"] = player
            except Exception:
                pass
        pane.set_items(items)
        pane.draw(self.screen, hitboxes=self._ui_hitboxes, key_prefix=prefix)

def draw_rule_button(self, rect: pygame.Rect, label: str, player, rule_type: str) -> None:
    is_active = False
    try:
        if self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
            if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == rule_type:
                is_active = True
    except Exception:
        is_active = False

    supported = False
    try:
        supported = self._get_rule_support_state(player, rule_type)
    except Exception:
        supported = False

    bg = (100, 149, 237) if is_active else (60, 60, 67)
    fg = (255, 255, 255)
    pygame.draw.rect(self.screen, bg, rect)
    pygame.draw.rect(self.screen, (63, 63, 70), rect, 1)
    try:
        font = pygame.font.SysFont('Arial', 14, bold=True)
    except Exception:
        font = pygame.font.Font(None, 14)
    text = font.render(label, True, fg)
    self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    if supported:
        try:
            badge_font = pygame.font.SysFont('Arial', 10, bold=True)
        except Exception:
            badge_font = pygame.font.Font(None, 10)
        badge_text = badge_font.render("SUP", True, fg)
        pad = 4
        badge_rect = pygame.Rect(
            rect.right - badge_text.get_width() - pad * 2 - 4,
            rect.y + 4,
            badge_text.get_width() + pad * 2,
            badge_text.get_height() + 2,
        )
        pygame.draw.rect(self.screen, (60, 160, 90), badge_rect, border_radius=3)
        self.screen.blit(badge_text, (badge_rect.x + pad, badge_rect.y + 1))

def draw_scroll_text_box(self, rect: pygame.Rect, lines, key: str, title: str = "Logs") -> None:
    if lines is None:
        lines = []
    elif isinstance(lines, (list, tuple)):
        lines = list(lines)
    else:
        lines = [lines]
    pygame.draw.rect(self.screen, (40,40,44), rect)
    pygame.draw.rect(self.screen, (70,70,78), rect, 1)
    try:
        msg_font = pygame.font.SysFont('Consolas', 12)
        title_font = pygame.font.SysFont('Arial', 14, bold=True)
    except Exception:
        msg_font = pygame.font.Font(None, 12)
        title_font = pygame.font.Font(None, 14)
    # Title
    ts = title_font.render(title, True, (220,220,230))
    self.screen.blit(ts, (rect.x + 6, rect.y + 4))

    # Word-wrap all lines into wrapped_lines list
    content_left = rect.x + 6
    content_top = rect.y + 24
    content_width = rect.width - 12
    content_height = rect.height - (content_top - rect.y) - 6

    def wrap_text(text: str) -> list:
        words = text.split(' ')
        wrapped = []
        line = ''
        for w in words:
            test = (line + ' ' + w).strip()
            surf = msg_font.render(test, True, (0,0,0))
            if surf.get_width() > content_width and line:
                wrapped.append(line)
                line = w
            else:
                line = test
        if line:
            wrapped.append(line)
        return wrapped

    wrapped_lines = []
    for ln in lines:
        wrapped_lines.extend(wrap_text(str(ln)))

    # Determine how many wrapped lines fit and apply scroll offset (from bottom)
    line_height = msg_font.get_height() + 2
    max_visible = max(0, content_height // line_height)
    scroll_state = getattr(self, "_bottom_log_scroll", None)
    if not isinstance(scroll_state, dict):
        scroll_state = {}
    offset = int(scroll_state.get(key, 0) or 0)
    start_index = max(0, len(wrapped_lines) - max_visible - offset)
    end_index = len(wrapped_lines) - offset if offset > 0 else len(wrapped_lines)
    to_show = wrapped_lines[start_index:end_index]

    # Draw from bottom up for consistent feel with logs
    y_cursor = rect.y + rect.height - 6
    for line in reversed(to_show):
        surf = msg_font.render(line, True, (200,200,200))
        y_cursor -= line_height
        if y_cursor < content_top:
            break
        self.screen.blit(surf, (content_left, y_cursor))
