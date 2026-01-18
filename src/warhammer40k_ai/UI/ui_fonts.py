from __future__ import annotations

from functools import lru_cache
from typing import Optional, Sequence

import pygame


_UI_FONT_CANDIDATES: Sequence[str] = (
    "Segoe UI Variable",
    "Segoe UI",
    "Noto Sans",
    "Inter",
    "Roboto",
    "Helvetica Neue",
    "Helvetica",
    "Arial",
)

_MONO_FONT_CANDIDATES: Sequence[str] = (
    "Cascadia Mono",
    "Consolas",
    "JetBrains Mono",
    "Menlo",
    "Monaco",
    "Courier New",
)


@lru_cache(maxsize=8)
def _resolve_font_path(bold: bool, mono: bool) -> Optional[str]:
    candidates = _MONO_FONT_CANDIDATES if mono else _UI_FONT_CANDIDATES
    try:
        return pygame.font.match_font(candidates, bold=bold)
    except Exception:
        return None


@lru_cache(maxsize=128)
def get_ui_font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    """Return a cached UI font with a consistent, readable family."""
    try:
        pygame.font.init()
    except Exception:
        pass

    path = _resolve_font_path(bool(bold), bool(mono))
    if path:
        try:
            return pygame.font.Font(path, int(size))
        except Exception:
            pass

    candidates = _MONO_FONT_CANDIDATES if mono else _UI_FONT_CANDIDATES
    try:
        return pygame.font.SysFont(candidates, int(size), bold=bool(bold))
    except Exception:
        return pygame.font.Font(None, int(size))
