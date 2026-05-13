from __future__ import annotations

import hashlib
import json
from typing import Any

from .command_kinds import CMD_RESOLVE_DECISION
from .commands import GameCommand
from .decisions import DecisionResult
from .ref_codec import encode_refs
from ..utility.game_context import game_context

def _canonical_command_event_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _command_event_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_command_event_json(value).encode("utf-8")).hexdigest()

def _command_rejection_diagnostics(
    game: "Game",
    command: GameCommand | None,
    *,
    encoded_payload: dict[str, Any],
    encoded_metadata: dict[str, Any],
    result: object | None,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    errors = [str(err or "") for err in list(getattr(result, "errors", ()) or ()) if str(err or "")]
    if errors:
        diagnostics["errors"] = errors
    if str(getattr(command, "kind", "") or "") != CMD_RESOLVE_DECISION:
        return diagnostics
    decision_id = str(encoded_payload.get("decision_id", "") or "")
    option_id = str(encoded_payload.get("option_id", "") or "")
    diagnostics["decision_id"] = decision_id
    diagnostics["option_id"] = option_id
    queue = getattr(game, "decision_queue", None)
    request = queue.get(decision_id) if queue is not None and hasattr(queue, "get") and decision_id else None
    decision_type = str(getattr(request, "decision_type", "") or "")
    if decision_type:
        diagnostics["decision_type"] = decision_type
    candidate_action_id = str(encoded_metadata.get("candidate_action_id", "") or "")
    if candidate_action_id:
        diagnostics["candidate_action_id"] = candidate_action_id
    candidate_kind = str(encoded_metadata.get("candidate_kind", "") or "")
    if candidate_kind:
        diagnostics["candidate_kind"] = candidate_kind
    result_payload = dict(encoded_payload.get("result_payload", {}) or {})
    diagnostics["payload_keys"] = sorted(str(key) for key in result_payload.keys())
    model_positions = result_payload.get("model_positions")
    if isinstance(model_positions, list):
        diagnostics["model_positions_count"] = int(len(model_positions))
        diagnostics["model_positions_checksum"] = _command_event_digest(model_positions)
    declarations = result_payload.get("declarations")
    if isinstance(declarations, list):
        diagnostics["declarations_count"] = int(len(declarations))
        diagnostics["declarations_checksum"] = _command_event_digest(declarations)
    return diagnostics

def _record_rejected_resolve_decision_command(
    game: "Game",
    command: GameCommand | None,
    result: object | None,
) -> None:
    if game is None or command is None or result is None:
        return
    if str(getattr(command, "kind", "") or "") != CMD_RESOLVE_DECISION:
        return
    if bool(getattr(result, "ok", False)):
        return
    payload = dict(getattr(command, "payload", {}) or {})
    decision_id = str(payload.get("decision_id", "") or "")
    if not decision_id:
        return
    queue = getattr(game, "decision_queue", None)
    request = queue.get(decision_id) if queue is not None and hasattr(queue, "get") else None
    if request is None:
        return
    raw_result_payload = payload.get("result_payload", {})
    result_payload = dict(raw_result_payload or {}) if isinstance(raw_result_payload, dict) else {}
    decision_result = DecisionResult(
        decision_id=decision_id,
        player_id=getattr(command, "player_id", None),
        option_id=str(payload.get("option_id", "") or ""),
        payload=result_payload,
    )
    errors = [str(error or "") for error in list(getattr(result, "errors", ()) or ()) if str(error or "")]
    game.decision_record_store.record_resolution(
        request,
        decision_result,
        ok=False,
        errors=errors,
        value=getattr(result, "value", None),
    )
    recorder = getattr(game, "_decision_replay_recorder", None)
    record_resolution = getattr(recorder, "record_resolution", None)
    if callable(record_resolution):
        record_resolution(game, request, decision_result, defer_keyframe=True)

class GameCommandService:
    def __init__(self, game: object) -> None:
        self.game = game

    def __deepcopy__(self, memo):
        return self

    def enqueue_command(self, command: GameCommand) -> None:
        """Queue a structured command for later processing."""
        if command is None:
            return
        self.game.command_queue.append(command)

    def _enter_command_context(self) -> None:
        depth = int(getattr(self.game, "_command_context_depth", 0) or 0)
        self.game._command_context_depth = depth + 1

    def _exit_command_context(self) -> None:
        depth = int(getattr(self.game, "_command_context_depth", 0) or 0)
        self.game._command_context_depth = max(0, depth - 1)

    def in_command_context(self) -> bool:
        return int(getattr(self.game, "_command_context_depth", 0) or 0) > 0

    def _maybe_queue_post_command_tool_decisions(self, command: GameCommand, result) -> bool:
        game = self.game
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        if not bool(getattr(result, "ok", False)):
            return False
        if not bool(getattr(game, "setup_complete", True)):
            return False
        queue = getattr(game, "decision_queue", None)
        list_fn = getattr(queue, "list", None) if queue is not None else None
        def _pending_not_in_progress() -> list[object]:
            if not callable(list_fn):
                return []
            return [
                request
                for request in list(list_fn() or [])
                if not bool(getattr(request, "_resolution_in_progress", False))
            ]

        if _pending_not_in_progress():
            return False

        current_player = None
        if list(getattr(game, "players", []) or []):
            current_player = game.get_current_player()

        non_current_players = [
            player
            for player in list(getattr(game, "players", []) or [])
            if player is not None and player is not current_player
        ]
        current_then_others = ([] if current_player is None else [current_player]) + non_current_players
        others_then_current = non_current_players + ([] if current_player is None else [current_player])

        def _queue_for_players(players, *, reactions_only: bool) -> bool:
            for player in list(players or []):
                manager = getattr(player, "stratagems", None)
                queue_tool_actions = getattr(manager, "queue_headless_tool_action_decision", None)
                if not callable(queue_tool_actions):
                    continue
                if bool(queue_tool_actions(reactions_only=bool(reactions_only))):
                    return True
            return False

        if _queue_for_players(others_then_current, reactions_only=True):
            return True
        if _pending_not_in_progress():
            return True
        if int(getattr(game, "_pre_attack_reaction_window_depth", 0) or 0) > 0:
            return False
        return _queue_for_players(current_then_others, reactions_only=False)

    def apply_command(self, command: GameCommand):
        """Validate and apply a command; returns CommandResult."""
        from .command_dispatcher import dispatch_command

        game = self.game
        with game_context(game):
            result = dispatch_command(game, command)
        event_log = getattr(game, "event_log", None)
        if event_log is not None and command is not None:
            encoded_payload = encode_refs(getattr(command, "payload", {}) or {})
            encoded_metadata = encode_refs(getattr(command, "metadata", {}) or {})
            payload = {
                "command_id": getattr(command, "command_id", ""),
                "kind": getattr(command, "kind", ""),
                "command_kind": getattr(command, "kind", ""),
                "player_id": getattr(command, "player_id", None),
                "payload": encoded_payload,
                "metadata": encoded_metadata,
            }
            event_type = "command_applied" if getattr(result, "ok", False) else "command_rejected"
            if event_type == "command_rejected":
                payload.update(
                    _command_rejection_diagnostics(
                        game,
                        command,
                        encoded_payload=encoded_payload,
                        encoded_metadata=encoded_metadata,
                        result=result,
                    )
                )
            event_log.record(
                event_type,
                actor_id=payload.get("player_id"),
                payload=payload,
                validate_payload=False,
            )
        _record_rejected_resolve_decision_command(game, command, result)
        recorder = getattr(game, "_decision_replay_recorder", None)
        record_post_command = getattr(recorder, "record_post_command", None)
        if callable(record_post_command):
            record_post_command(game, command, result)
        post_command_fn = getattr(game, "_maybe_queue_post_command_tool_decisions", None)
        default_post_command_fn = getattr(type(game), "_maybe_queue_post_command_tool_decisions", None)
        is_default_wrapper = getattr(post_command_fn, "__func__", None) is default_post_command_fn
        if callable(post_command_fn) and not is_default_wrapper:
            post_command_fn(command, result)
        else:
            self._maybe_queue_post_command_tool_decisions(command, result)
        return result

    def process_command_queue(self, *, limit: int | None = None):
        """Process queued commands in order; returns list of CommandResult."""
        results = []
        remaining = None if limit is None else int(limit)
        while self.game.command_queue and (remaining is None or remaining > 0):
            cmd = self.next_command()
            if cmd is None:
                break
            results.append(self.apply_command(cmd))
            if remaining is not None:
                remaining -= 1
        return results

    def next_command(self) -> GameCommand | None:
        """Pop the next queued command, if any."""
        if not self.game.command_queue:
            return None
        return self.game.command_queue.pop(0)
