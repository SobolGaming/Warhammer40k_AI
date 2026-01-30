from __future__ import annotations

from typing import Optional

from ..engine.decision_controller import DecisionController
from ..engine.decisions import DecisionRequest


class UIDecisionController(DecisionController):
    def __init__(self, game_view: object, *, player_id: Optional[str] = None) -> None:
        super().__init__(player_id=player_id)
        self._game_view = game_view

    def handles_player(self, player_id: Optional[str]) -> bool:
        game = getattr(self._game_view, "game", None)
        if game is None:
            return False
        if player_id is None:
            return True
        try:
            player = game._resolve_player_by_id(player_id)
        except Exception:
            player = None
        if player is None:
            for p in list(getattr(game, "players", []) or []):
                if getattr(p, "id", None) == player_id:
                    player = p
                    break
        if player is None:
            return False
        try:
            return bool(player.has_control())
        except Exception:
            return False

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        handler = getattr(self._game_view, "_on_decision_requested", None)
        if callable(handler):
            handler(request=request, game=game)
