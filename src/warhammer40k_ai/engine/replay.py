from __future__ import annotations

from typing import Iterable, List

from .commands import GameCommand
from .event_log import DeterministicEventLog
from .decisions import DecisionResult
from .snapshot import load_game_snapshot


def prepare_replay(snapshot: dict, event_tail: Iterable[dict]) -> "Game":
    """Load a snapshot and attach a deterministic event log in replay mode."""
    game = load_game_snapshot(snapshot)
    existing_log = getattr(game, "event_log", None)
    if existing_log is not None:
        existing_log.detach()
    replay_log = DeterministicEventLog.from_payload(list(event_tail or []), mode="replay")
    replay_log.attach(game)
    game.event_log = replay_log
    return game


def replay_commands(
    snapshot: dict,
    event_tail: Iterable[dict],
    commands: Iterable[GameCommand | dict],
) -> tuple["Game", List[object]]:
    """Replay commands against a snapshot using an event tail for deterministic validation."""
    game = prepare_replay(snapshot, event_tail)
    results: List[object] = []
    for cmd in list(commands or []):
        if isinstance(cmd, dict):
            cmd_obj = GameCommand.from_dict(cmd)
        else:
            cmd_obj = cmd
        results.append(game.apply_command(cmd_obj))
    return game, results


def replay_from_event_log(
    snapshot: dict,
    event_tail: Iterable[dict],
    commands: Iterable[GameCommand | dict],
) -> tuple["Game", List[object]]:
    return replay_commands(snapshot, event_tail, commands)


def replay_decisions(
    snapshot: dict,
    decisions: Iterable[DecisionResult | dict],
    *,
    event_tail: Iterable[dict] | None = None,
) -> tuple["Game", List[object]]:
    tail = list(event_tail or [])
    game = prepare_replay(snapshot, tail)
    results: List[object] = []
    for entry in list(decisions or []):
        if isinstance(entry, dict):
            result = DecisionResult.from_dict(entry)
        else:
            result = entry
        results.append(game.resolve_decision(result))
    return game, results
