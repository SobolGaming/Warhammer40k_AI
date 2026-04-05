from __future__ import annotations

from collections.abc import Sequence

DEFAULT_PLAYER_UI_COLOR_PALETTE: tuple[tuple[int, int, int], ...] = (
    (57, 255, 20),
    (255, 72, 72),
    (72, 170, 255),
    (255, 200, 60),
    (190, 120, 255),
    (70, 220, 210),
)


def _normalize_rgb_triplet(rgb: Sequence[int]) -> list[int]:
    values = list(rgb or [])
    if len(values) != 3:
        raise ValueError("Player UI color must contain exactly 3 RGB components.")
    normalized: list[int] = []
    for idx, value in enumerate(values):
        ivalue = int(value)
        if ivalue < 0 or ivalue > 255:
            raise ValueError(f"RGB component index {idx} out of range: {ivalue}")
        normalized.append(ivalue)
    return normalized


def _normalize_hue_degrees(hue_degrees: int | None) -> int | None:
    if hue_degrees is None:
        return None
    value = int(hue_degrees)
    if value < 0 or value >= 360:
        raise ValueError(f"Hue degrees must be within [0, 359], got {value}")
    return value


def initialize_player_ui_state(player) -> None:
    player.ui_color_rgb = [0, 0, 0]
    player.ui_color_hue_degrees = None
    player.ui_color_selected = False
    player.ui_color_source = "default"


class PlayerUIMixin:
    def set_ui_color(
        self,
        rgb: Sequence[int],
        *,
        hue_degrees: int | None = None,
        selected: bool = True,
        source: str = "custom",
    ) -> None:
        self.ui_color_rgb = _normalize_rgb_triplet(rgb)
        self.ui_color_hue_degrees = _normalize_hue_degrees(hue_degrees)
        self.ui_color_selected = bool(selected)
        self.ui_color_source = str(source or "custom")

    def assign_default_ui_color(self, slot_index: int) -> None:
        idx = int(slot_index or 0)
        palette = DEFAULT_PLAYER_UI_COLOR_PALETTE
        color = palette[idx % len(palette)]
        self.set_ui_color(color, hue_degrees=None, selected=False, source="default")

    def get_ui_color_rgb(self) -> tuple[int, int, int]:
        rgb = _normalize_rgb_triplet(self.ui_color_rgb)
        self.ui_color_rgb = list(rgb)
        return (rgb[0], rgb[1], rgb[2])
