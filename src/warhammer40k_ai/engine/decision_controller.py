from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .decision_kinds import DECISION_CONFIRM_YES_NO
from .decisions import DecisionRequest, DecisionResult


class DecisionController(ABC):
    """Controller interface for human UI, remote clients, or headless agents."""

    def __init__(self, *, player_id: Optional[str] = None) -> None:
        self._player_id = player_id

    def handles_player(self, player_id: Optional[str]) -> bool:
        if self._player_id is None:
            return True
        return str(self._player_id) == str(player_id or "")

    def supports_generic_tool_decisions(self) -> bool:
        return False

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
        self._dispatching_pending_head = False

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
        if not self._request_can_dispatch(game, request):
            return
        self._dispatch_request(game, request)

    def _dispatch_request(self, game: object, request: DecisionRequest) -> bool:
        player_id = getattr(request, "player_id", None)
        dispatched = False
        for controller in list(self._controllers):
            if not self._request_can_dispatch(game, request):
                break
            if controller.handles_player(player_id):
                dispatched = True
                controller.on_decision_requested(game, request)
        return dispatched

    def _on_decision_resolved(self, request=None, result=None, game=None, **_kwargs) -> None:
        if request is None or result is None:
            return
        game = game or self._game
        player_id = getattr(request, "player_id", None)
        for controller in list(self._controllers):
            if controller.handles_player(player_id):
                controller.on_decision_resolved(game, request, result)
        self._dispatch_pending_head(game)

    def _dispatch_pending_head(self, game: object) -> None:
        if self._dispatching_pending_head:
            return
        queue = getattr(game, "decision_queue", None)
        peek = getattr(queue, "peek", None)
        if not callable(peek):
            return
        self._dispatching_pending_head = True
        try:
            while True:
                request = peek()
                if request is None:
                    return
                decision_id = str(getattr(request, "decision_id", "") or "")
                dispatched = self._dispatch_request(game, request)
                if not dispatched:
                    return
                current = peek()
                current_id = str(getattr(current, "decision_id", "") or "") if current is not None else ""
                if current_id == decision_id:
                    return
        finally:
            self._dispatching_pending_head = False

    @staticmethod
    def _request_is_pending(game: object, request: DecisionRequest) -> bool:
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "get"):
            return True
        decision_id = str(getattr(request, "decision_id", "") or "")
        if not decision_id:
            return True
        return queue.get(decision_id) is not None

    @staticmethod
    def _request_is_current(game: object, request: DecisionRequest) -> bool:
        if not DecisionControllerHub._request_is_pending(game, request):
            return False
        queue = getattr(game, "decision_queue", None)
        peek = getattr(queue, "peek", None)
        if not callable(peek):
            return True
        current = peek()
        if current is None:
            return False
        decision_id = str(getattr(request, "decision_id", "") or "")
        current_id = str(getattr(current, "decision_id", "") or "")
        if not decision_id:
            return True
        return current_id == decision_id

    @staticmethod
    def _request_can_dispatch(game: object, request: DecisionRequest) -> bool:
        if DecisionControllerHub._request_is_current(game, request):
            return True
        if not DecisionControllerHub._request_is_pending(game, request):
            return False
        if int(getattr(game, "_decision_resolution_depth", 0) or 0) <= 0:
            return False
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type != DECISION_CONFIRM_YES_NO:
            return False
        context = dict(getattr(request, "context", {}) or {})
        return bool(context.get("optional", False)) or bool(context.get("synchronous", False))
