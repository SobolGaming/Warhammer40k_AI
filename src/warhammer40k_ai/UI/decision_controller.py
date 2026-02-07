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
        resolve_player = getattr(game, "_resolve_player_by_id", None)
        player = resolve_player(player_id) if callable(resolve_player) else None
        if player is None:
            for p in list(getattr(game, "players", []) or []):
                if getattr(p, "id", None) == player_id:
                    player = p
                    break
        if player is None:
            return False
        has_control = getattr(player, "has_control", None)
        return bool(has_control()) if callable(has_control) else False

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        handler = getattr(self._game_view, "_on_decision_requested", None)
        if callable(handler):
            handler(request=request, game=game)
