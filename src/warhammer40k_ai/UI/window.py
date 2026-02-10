from __future__ import annotations

import os
import sys
from typing import Tuple

import pygame
import logging
logger = logging.getLogger(__name__)


def _desired_window_size() -> Tuple[int, int]:
    from .game_ui import (
        ROSTER_PANE_WIDTH,
        STRATAGEM_PANE_WIDTH,
        BATTLEFIELD_WIDTH,
        BATTLEFIELD_HEIGHT,
        INFO_PANE_HEIGHT,
        TILE_SIZE,
    )

    desired_width = BATTLEFIELD_WIDTH + 2 * (ROSTER_PANE_WIDTH + STRATAGEM_PANE_WIDTH)
    top_pane_height = int(2 * TILE_SIZE)
    desired_height = BATTLEFIELD_HEIGHT + INFO_PANE_HEIGHT + top_pane_height
    return int(desired_width), int(desired_height)


def _get_target_display_size(desired_width: int, desired_height: int) -> Tuple[int, int]:
    info = pygame.display.Info()
    fallback_w, fallback_h = int(info.current_w), int(info.current_h)

    try:
        if hasattr(pygame.display, "get_window_position"):
            wx, wy = pygame.display.get_window_position()
        else:
            return fallback_w, fallback_h

        if hasattr(pygame.display, "get_num_displays") and hasattr(pygame.display, "get_display_bounds"):
            num = int(pygame.display.get_num_displays())
            cx = int(wx + desired_width // 2)
            cy = int(wy + desired_height // 2)
            for i in range(num):
                bx, by, bw, bh = pygame.display.get_display_bounds(i)
                if bx <= cx < bx + bw and by <= cy < by + bh:
                    return int(bw), int(bh)
    except Exception:
        pass

    try:
        if hasattr(pygame.display, "get_desktop_sizes"):
            desktop_sizes = pygame.display.get_desktop_sizes()
            if desktop_sizes:
                best_w, best_h = max(desktop_sizes, key=lambda s: int(s[0]) * int(s[1]))
                return int(best_w), int(best_h)
    except Exception:
        pass

    return fallback_w, fallback_h


def create_pygame_screen(*, title: str = "Warhammer 40,000 Battlefield") -> pygame.Surface:
    pygame.init()
    desired_width, desired_height = _desired_window_size()
    screen = pygame.display.set_mode((desired_width, desired_height), pygame.RESIZABLE)
    pygame.display.set_caption(title)

    monitor_width, monitor_height = _get_target_display_size(desired_width, desired_height)

    margin_w = 100
    margin_h = 150
    if sys.platform == "darwin":
        margin_w = 40
        margin_h = 60

    usable_width = max(1, monitor_width - margin_w)
    usable_height = max(1, monitor_height - margin_h)
    scale_factor = min(1.0, usable_width / desired_width, usable_height / desired_height)

    if (desired_width <= monitor_width and desired_height <= monitor_height) and scale_factor < 1.0:
        scale_factor = 1.0

    if os.environ.get("WH_UI_DISPLAY_DEBUG", "").strip():
        try:
            info = pygame.display.Info()
            logger.debug(f"Display debug: desired={desired_width}x{desired_height} "
                f"info={int(info.current_w)}x{int(info.current_h)} "
                f"chosen_display={monitor_width}x{monitor_height} "
                f"usable={usable_width}x{usable_height} "
                f"scale={scale_factor:.2f}")
        except Exception:
            pass

    if scale_factor < 1.0:
        actual_width = int(desired_width * scale_factor)
        actual_height = int(desired_height * scale_factor)
        logger.info(f"Scaling window to fit display: {desired_width}x{desired_height} -> "
            f"{actual_width}x{actual_height} (scale: {scale_factor:.2f})")
        screen = pygame.display.set_mode((actual_width, actual_height), pygame.RESIZABLE)
    else:
        logger.info(f"Using full size window: {desired_width}x{desired_height}")
    return screen
