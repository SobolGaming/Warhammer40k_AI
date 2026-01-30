from __future__ import annotations

from typing import Optional

from ..engine.command_kinds import CMD_RESOLVE_DECISION
from ..engine.commands import GameCommand
from ..engine.decision_controller import DecisionController
from ..engine.decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL
from ..engine.decisions import DecisionRequest


class AutoDiceDecisionController(DecisionController):
    def __init__(self, session) -> None:
        super().__init__(player_id=None)
        self._session = session

    def on_decision_requested(self, game: object, request: DecisionRequest) -> None:
        if request is None:
            return
        if not self._session.allow_commands:
            return
        if not bool(getattr(game, "auto_resolve_dice_rolls", False)):
            return
        dtype = getattr(request, "decision_type", None)
        if dtype not in (DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL):
            return
        player_id = getattr(request, "player_id", None)
        player = None
        try:
            registry = getattr(game, "entity_registry", None)
            if registry is not None:
                player = registry.get(str(player_id), kind="player")
        except Exception:
            player = None
        if player is None:
            for p in list(getattr(game, "players", []) or []):
                if getattr(p, "id", None) == player_id:
                    player = p
                    break
        if player is None:
            return
        try:
            if not player.has_control():
                return
        except Exception:
            return

        option_id: Optional[str] = None
        result_payload = {}
        if dtype == DECISION_REQUEST_DICE_ROLL:
            for opt in list(getattr(request, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if str(payload.get("action_id", "")) == "roll":
                    option_id = opt.option_id
                    break
            if option_id is None and getattr(request, "options", None):
                option_id = request.options[0].option_id
        else:
            mgr = getattr(game, "roll_manager", None)
            ctx = dict(getattr(request, "context", {}) or {})
            roll_id = ctx.get("roll_id")
            state = None
            if mgr is not None and roll_id is not None:
                try:
                    state = mgr.get_roll(int(roll_id))
                except Exception:
                    state = None
            action_id, selected = ("none", [])
            if mgr is not None and state is not None:
                try:
                    action_id, selected = mgr._auto_pick_reroll_action(game, state)
                except Exception:
                    action_id, selected = ("none", [])
            for opt in list(getattr(request, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if str(payload.get("action_id", "")) == str(action_id):
                    option_id = opt.option_id
                    break
            if option_id is None and getattr(request, "options", None):
                option_id = request.options[0].option_id
            if selected is not None:
                result_payload["selected_die_ids"] = list(selected)

        if not option_id:
            return
        cmd = GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=player_id,
            payload={"decision_id": request.decision_id, "option_id": option_id, "result_payload": result_payload},
        )
        self._session.queue_command(cmd)
