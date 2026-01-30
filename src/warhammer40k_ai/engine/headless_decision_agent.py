from __future__ import annotations

from typing import Optional

from .decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
from .decision_controller import DecisionController
from ..utility.decision_utils import resolve_decision_command


class HeadlessDecisionAgent(DecisionController):
    """Auto-resolve dice roll decisions for authoritative/headless games."""

    def __init__(self, game: object, *, group: str = "headless:auto_decisions") -> None:
        super().__init__(player_id=None)
        self._game = game
        self._group = str(group or "headless:auto_decisions")
        self._attached = False
        self.attach()

    def attach(self) -> None:
        if self._attached:
            return
        add_controller = getattr(self._game, "add_decision_controller", None)
        if callable(add_controller):
            add_controller(self)
            self._attached = True
            return
        event_system = getattr(self._game, "event_system", None)
        if event_system is None:
            return
        event_system.subscribe("decision_requested", self._on_decision_requested, group=self._group)
        self._attached = True

    def detach(self) -> None:
        if not self._attached:
            return
        event_system = getattr(self._game, "event_system", None)
        if event_system is None:
            return
        try:
            event_system.unsubscribe_group(self._group)
        except Exception:
            pass
        self._attached = False

    def on_decision_requested(self, game: object, request) -> None:
        self._on_decision_requested(request=request, game=game)

    def _on_decision_requested(self, request=None, game=None, **_kwargs) -> None:
        game = game or self._game
        if request is None or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not bool(getattr(game, "auto_resolve_dice_rolls", False)):
            return
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type == DECISION_REQUEST_DICE_ROLL:
            self._auto_resolve_roll(request, game)
        elif decision_type == DECISION_SELECT_DICE_REROLL:
            self._auto_resolve_reroll(request, game)

    def _auto_resolve_roll(self, request, game: object) -> None:
        option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("action_id", "") or "") == "roll":
                option_id = opt.option_id
                break
        if option_id is None and getattr(request, "options", None):
            option_id = request.options[0].option_id
        if not option_id:
            return
        resolve_decision_command(
            game,
            request,
            option_id,
            result_payload={},
            player_id=getattr(request, "player_id", None),
        )

    def _auto_resolve_reroll(self, request, game: object) -> None:
        mgr = getattr(game, "roll_manager", None)
        if mgr is None:
            return
        ctx = dict(getattr(request, "context", {}) or {})
        roll_id = ctx.get("roll_id")
        state = None
        if roll_id is not None:
            try:
                state = mgr.get_roll(int(roll_id))
            except Exception:
                state = None
        action_id, selected = ("none", [])
        try:
            if state is not None:
                action_id, selected = mgr._auto_pick_reroll_action(game, state)
        except Exception:
            action_id, selected = ("none", [])
        option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("action_id", "") or "") == str(action_id):
                option_id = opt.option_id
                break
        if option_id is None and getattr(request, "options", None):
            option_id = request.options[0].option_id
        if not option_id:
            return
        payload = {}
        if selected is not None:
            payload["selected_die_ids"] = list(selected)
        resolve_decision_command(
            game,
            request,
            option_id,
            result_payload=payload,
            player_id=getattr(request, "player_id", None),
        )
