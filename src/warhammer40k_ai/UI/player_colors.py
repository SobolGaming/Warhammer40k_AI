from __future__ import annotations

from typing import Any, Iterable, Optional, Tuple

from .ui_constants import (
    DARK_GREY,
    PLAYER_ACTIVE_HEADER_BLEND,
    PLAYER_UI_FALLBACK_RGB,
    PLAYER_ZONE_ALPHA,
    PLAYER_ZONE_BORDER_SHADE,
)


def _clamp_channel(value: object) -> int:
    return max(0, min(255, int(value)))


def _normalize_rgb(rgb: object, *, fallback: Tuple[int, int, int]) -> Tuple[int, int, int]:
    if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
        return (_clamp_channel(rgb[0]), _clamp_channel(rgb[1]), _clamp_channel(rgb[2]))
    return (_clamp_channel(fallback[0]), _clamp_channel(fallback[1]), _clamp_channel(fallback[2]))


def _blend_rgb(base: Tuple[int, int, int], overlay: Tuple[int, int, int], ratio: float) -> Tuple[int, int, int]:
    mix = max(0.0, min(1.0, float(ratio)))
    return (
        _clamp_channel(round(base[0] * (1.0 - mix) + overlay[0] * mix)),
        _clamp_channel(round(base[1] * (1.0 - mix) + overlay[1] * mix)),
        _clamp_channel(round(base[2] * (1.0 - mix) + overlay[2] * mix)),
    )


def _shade_rgb(rgb: Tuple[int, int, int], shade: float) -> Tuple[int, int, int]:
    scale = max(0.0, min(1.0, float(shade)))
    return (
        _clamp_channel(round(rgb[0] * scale)),
        _clamp_channel(round(rgb[1] * scale)),
        _clamp_channel(round(rgb[2] * scale)),
    )


def resolve_game_player_by_id(game: object, player_id: object) -> Optional[object]:
    pid = str(player_id or "")
    if not pid or game is None:
        return None
    players: Iterable[object] = list(getattr(game, "players", []) or [])
    for player in players:
        if str(getattr(player, "id", "") or "") == pid:
            return player
    return None


def get_player_color_rgb(
    player: object,
    *,
    fallback: Tuple[int, int, int] = PLAYER_UI_FALLBACK_RGB,
) -> Tuple[int, int, int]:
    if player is None:
        return _normalize_rgb(fallback, fallback=fallback)
    getter = getattr(player, "get_ui_color_rgb", None)
    if callable(getter):
        return _normalize_rgb(getter(), fallback=fallback)
    return _normalize_rgb(getattr(player, "ui_color_rgb", None), fallback=fallback)


def get_active_roster_header_rgb(
    player: object,
    *,
    base_header_rgb: Tuple[int, int, int] = DARK_GREY,
    blend: float = PLAYER_ACTIVE_HEADER_BLEND,
) -> Tuple[int, int, int]:
    return _blend_rgb(_normalize_rgb(base_header_rgb, fallback=DARK_GREY), get_player_color_rgb(player), blend)


def get_zone_fill_rgba(player: object, *, alpha: int = PLAYER_ZONE_ALPHA) -> Tuple[int, int, int, int]:
    rgb = get_player_color_rgb(player)
    return (rgb[0], rgb[1], rgb[2], _clamp_channel(alpha))


def get_zone_border_rgb(player: object, *, shade: float = PLAYER_ZONE_BORDER_SHADE) -> Tuple[int, int, int]:
    return _shade_rgb(get_player_color_rgb(player), shade)


def get_contrasting_text_rgb(background_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    rgb = _normalize_rgb(background_rgb, fallback=DARK_GREY)
    luma = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return (20, 20, 20) if luma >= 150.0 else (255, 255, 255)

