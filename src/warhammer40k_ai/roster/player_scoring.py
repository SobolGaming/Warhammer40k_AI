from __future__ import annotations

from typing import Any


def initialize_player_scoring_state(player) -> None:
    player.score = 0
    player.vp_primary = 0
    player.vp_secondary = 0
    player.vp_battle_ready = 0
    player.vp_history = []
    player.is_battle_ready = True


class PlayerScoringMixin:
    def get_score(self) -> int:
        return self.score

    def add_score(self, points: int) -> None:
        self.score += points

    def get_vp_breakdown(self) -> dict[str, Any]:
        """Return a simple VP breakdown dict. Game logic is the authoritative scorer."""
        return {
            "total": int(self.score or 0),
            "primary": int(self.vp_primary or 0),
            "secondary": int(self.vp_secondary or 0),
            "battle_ready": int(self.vp_battle_ready or 0),
        }
