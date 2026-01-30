from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .decisions import DecisionRequest, DecisionResult


class DecisionController(ABC):
    """Controller interface for human UI, remote clients, or headless agents."""

    def __init__(self, *, player_id: Optional[str] = None) -> None:
        self._player_id = player_id

    def handles_player(self, player_id: Optional[str]) -> bool:
        if self._player_id is None:
            return True
        return str(self._player_id) == str(player_id or "")

    @abstractmethod
    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        raise NotImplementedError

    def on_decision_resolved(
        self,
        game: object,
        request: DecisionRequest,
        result: DecisionResult,
    ) -> None:
        return None


class DecisionControllerHub:
    def __init__(self, game: object) -> None:
        self._game = game
        self._controllers: List[DecisionController] = []
        self._attached = False

    def attach(self) -> None:
        if self._attached:
            return
        event_system = getattr(self._game, "event_system", None)
        if event_system is None:
            return
        event_system.subscribe("decision_requested", self._on_decision_requested, group="controller_hub")
        event_system.subscribe("decision_resolved", self._on_decision_resolved, group="controller_hub")
        self._attached = True

    def detach(self) -> None:
        if not self._attached:
            return
        event_system = getattr(self._game, "event_system", None)
        if event_system is None:
            return
        event_system.unsubscribe_group("controller_hub")
        self._attached = False

    def add_controller(self, controller: DecisionController) -> None:
        if controller in self._controllers:
            return
        self._controllers.append(controller)

    def remove_controller(self, controller: DecisionController) -> None:
        if controller in self._controllers:
            self._controllers.remove(controller)

    def _on_decision_requested(self, request=None, game=None, **_kwargs) -> None:
        if request is None:
            return
        game = game or self._game
        player_id = getattr(request, "player_id", None)
        for controller in list(self._controllers):
            if controller.handles_player(player_id):
                controller.on_decision_requested(game, request)

    def _on_decision_resolved(self, request=None, result=None, game=None, **_kwargs) -> None:
        if request is None or result is None:
            return
        game = game or self._game
        player_id = getattr(request, "player_id", None)
        for controller in list(self._controllers):
            if controller.handles_player(player_id):
                controller.on_decision_resolved(game, request, result)
