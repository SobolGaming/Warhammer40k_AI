from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_NEXT_PHASE,
    CMD_RESOLVE_DECISION,
    CMD_SELECT_MISSION,
    CMD_SET_DEPLOYMENT_WAITING,
)
from .commands import GameCommand
from .decisions import DecisionResult
from .decision_dispatcher import validate_decision

CommandValidator = Callable[[object, GameCommand], Sequence[str]]
CommandApplier = Callable[[object, GameCommand], Any]


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    kind: str
    ok: bool
    errors: tuple[str, ...] = ()
    value: Any = None


@dataclass(frozen=True)
class CommandHandler:
    kind: str
    validate: CommandValidator
    apply: CommandApplier


_HANDLERS: dict[str, CommandHandler] = {}


def register_command_handler(kind: str, *, validate: CommandValidator, apply: CommandApplier) -> None:
    if kind in _HANDLERS:
        raise ValueError(f"Command handler already registered: {kind}")
    _HANDLERS[kind] = CommandHandler(kind=kind, validate=validate, apply=apply)


def dispatch_command(game: object, command: GameCommand) -> CommandResult:
    if command is None:
        return CommandResult(command_id="", kind="", ok=False, errors=("Missing command",))
    handler = _HANDLERS.get(command.kind)
    if handler is None:
        return CommandResult(
            command_id=command.command_id,
            kind=command.kind,
            ok=False,
            errors=(f"Unknown command kind: {command.kind}",),
        )
    errors = tuple(handler.validate(game, command) or ())
    if errors:
        return CommandResult(command_id=command.command_id, kind=command.kind, ok=False, errors=errors)
    enter_ctx = getattr(game, "_enter_command_context", None)
    exit_ctx = getattr(game, "_exit_command_context", None)
    if callable(enter_ctx):
        enter_ctx()
    try:
        value = handler.apply(game, command)
    finally:
        if callable(exit_ctx):
            exit_ctx()
    return CommandResult(command_id=command.command_id, kind=command.kind, ok=True, value=value)


def _validate_next_phase(game: object, command: GameCommand) -> Sequence[str]:
    if not bool(getattr(game, "setup_complete", False)):
        return ("Setup phase not complete; cannot advance battle phases.",)
    return ()


def _apply_next_phase(game: object, command: GameCommand) -> None:
    from .turn_manager import next_phase as _next_phase

    _next_phase(game)
    return None


def _validate_execute_setup_phase(game: object, command: GameCommand) -> Sequence[str]:
    payload = command.payload or {}
    allowed = {"player1_army_file", "player2_army_file", "manual_phases"}
    extra = set(payload.keys()) - allowed
    if extra:
        return (f"Unsupported execute_setup_phase payload keys: {sorted(extra)}",)
    if "manual_phases" in payload and not isinstance(payload["manual_phases"], bool):
        return ("manual_phases must be a boolean.",)
    return ()


def _apply_execute_setup_phase(game: object, command: GameCommand) -> None:
    payload = command.payload or {}
    exec_fn = getattr(game, "_execute_current_setup_phase_impl", None)
    if not callable(exec_fn):
        raise RuntimeError("Game missing _execute_current_setup_phase_impl.")
    exec_fn(
        player1_army_file=payload.get("player1_army_file"),
        player2_army_file=payload.get("player2_army_file"),
        manual_phases=payload.get("manual_phases", False),
    )
    return None


def _validate_advance_setup_phase(game: object, command: GameCommand) -> Sequence[str]:
    return ()


def _apply_advance_setup_phase(game: object, command: GameCommand) -> bool:
    advance_fn = getattr(game, "_advance_setup_phase_impl", None)
    if not callable(advance_fn):
        raise RuntimeError("Game missing _advance_setup_phase_impl.")
    return bool(advance_fn())


def _validate_select_mission(game: object, command: GameCommand) -> Sequence[str]:
    payload = command.payload or {}
    combination = payload.get("combination")
    layout = payload.get("layout")
    if not isinstance(combination, dict):
        return ("Mission selection requires combination dict.",)
    if layout is None:
        return ("Mission selection requires layout.",)
    required = {"id", "primary", "deployment"}
    missing = required - set(combination.keys())
    if missing:
        return (f"Mission combination missing keys: {sorted(missing)}",)
    return ()


def _apply_select_mission(game: object, command: GameCommand) -> None:
    payload = command.payload or {}
    combination = payload.get("combination")
    layout = payload.get("layout")
    apply_fn = getattr(game, "_apply_selected_mission", None)
    if not callable(apply_fn):
        raise RuntimeError("Game missing _apply_selected_mission.")
    apply_fn(combination, layout)
    return None


def _validate_set_deployment_waiting(game: object, command: GameCommand) -> Sequence[str]:
    payload = command.payload or {}
    if "value" not in payload:
        return ("deployment waiting command requires 'value'.",)
    if not isinstance(payload.get("value"), bool):
        return ("deployment waiting value must be boolean.",)
    return ()


def _apply_set_deployment_waiting(game: object, command: GameCommand) -> None:
    payload = command.payload or {}
    setattr(game, "waiting_for_deployment_input", bool(payload.get("value")))
    return None


def _validate_resolve_decision(game: object, command: GameCommand) -> Sequence[str]:
    payload = command.payload or {}
    decision_id = payload.get("decision_id")
    option_id = payload.get("option_id")
    if not isinstance(decision_id, str) or not decision_id:
        return ("Decision resolution requires decision_id.",)
    if not isinstance(option_id, str) or not option_id:
        return ("Decision resolution requires option_id.",)
    queue = getattr(game, "decision_queue", None)
    if queue is None or not hasattr(queue, "get"):
        return ("Game missing decision_queue.",)
    request = queue.get(decision_id)
    if request is None:
        return (f"Decision not found: {decision_id}",)
    request_player = getattr(request, "player_id", None)
    if request_player is not None:
        if command.player_id is None:
            return ("Decision resolution requires player_id.",)
        if str(command.player_id) != str(request_player):
            return ("Decision belongs to another player.",)
    result_payload = payload.get("result_payload", {})
    if result_payload is not None and not isinstance(result_payload, dict):
        return ("result_payload must be a dict.",)
    result = DecisionResult(
        decision_id=str(decision_id or ""),
        player_id=command.player_id,
        option_id=str(option_id or ""),
        payload=dict(result_payload or {}),
    )
    return validate_decision(game, request, result)


def _apply_resolve_decision(game: object, command: GameCommand) -> None:
    payload = command.payload or {}
    decision_id = payload.get("decision_id")
    option_id = payload.get("option_id")
    result_payload = payload.get("result_payload", {}) or {}
    result = DecisionResult(
        decision_id=str(decision_id or ""),
        player_id=command.player_id,
        option_id=str(option_id or ""),
        payload=dict(result_payload),
    )
    resolve_fn = getattr(game, "resolve_decision", None)
    if not callable(resolve_fn):
        raise RuntimeError("Game missing resolve_decision.")
    return resolve_fn(result)


register_command_handler(CMD_NEXT_PHASE, validate=_validate_next_phase, apply=_apply_next_phase)
register_command_handler(CMD_EXECUTE_SETUP_PHASE, validate=_validate_execute_setup_phase, apply=_apply_execute_setup_phase)
register_command_handler(CMD_ADVANCE_SETUP_PHASE, validate=_validate_advance_setup_phase, apply=_apply_advance_setup_phase)
register_command_handler(CMD_SELECT_MISSION, validate=_validate_select_mission, apply=_apply_select_mission)
register_command_handler(CMD_SET_DEPLOYMENT_WAITING, validate=_validate_set_deployment_waiting, apply=_apply_set_deployment_waiting)
register_command_handler(CMD_RESOLVE_DECISION, validate=_validate_resolve_decision, apply=_apply_resolve_decision)
