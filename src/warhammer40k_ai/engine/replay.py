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


def _record_action_ids(record: dict) -> set[str]:
    action_ids: set[str] = set()
    for candidate in list(record.get("candidates", []) or []):
        action_id = str(dict(candidate or {}).get("action_id", "") or "")
        if action_id:
            action_ids.add(action_id)
    return action_ids


def _build_result_from_decision_record(request, record: dict) -> DecisionResult:
    valid = bool(record.get("valid", True))
    if not valid:
        raise ValueError("DecisionRecord replay only supports valid=true records.")
    chosen_action_id = str(record.get("chosen_action_id", "") or "")
    if not chosen_action_id:
        raise ValueError("DecisionRecord is missing chosen_action_id.")
    chosen_option_id = None
    for option in list(getattr(request, "options", []) or []):
        option_id = getattr(option, "option_id", None)
        action_id = request.action_id_for_option_id(option_id)
        if str(action_id) == chosen_action_id:
            chosen_option_id = option_id
            break
    chosen_candidate = None
    for candidate in list(record.get("candidates", []) or []):
        payload = dict(candidate or {})
        if str(payload.get("action_id", "") or "") == chosen_action_id:
            chosen_candidate = payload
            break
    if chosen_option_id is not None:
        return DecisionResult(
            decision_id=str(getattr(request, "decision_id", "") or ""),
            player_id=getattr(request, "player_id", None),
            option_id=chosen_option_id,
            payload={},
        )
    if not bool(record.get("human_action_injected", False)):
        raise ValueError("chosen_action_id does not map to an option_id for this request.")
    if chosen_candidate is None:
        raise ValueError("Chosen action is missing from DecisionRecord candidates.")
    fallback_option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").lower() == "skip":
            continue
        fallback_option_id = getattr(option, "option_id", None)
        if fallback_option_id:
            break
    if fallback_option_id is None and list(getattr(request, "options", []) or []):
        fallback_option_id = getattr(request.options[0], "option_id", None)
    if fallback_option_id is None:
        raise ValueError("Decision request has no selectable option for injected human action replay.")
    params = dict(chosen_candidate.get("params", {}) or {})
    payload = dict(params)
    payload["human_action_params"] = dict(params)
    return DecisionResult(
        decision_id=str(getattr(request, "decision_id", "") or ""),
        player_id=getattr(request, "player_id", None),
        option_id=fallback_option_id,
        payload=payload,
    )


def _assert_strict_candidate_match(request, record: dict) -> None:
    expected_candidates = [candidate.to_dict() for candidate in list(getattr(request, "candidates", []) or [])]
    expected_mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
    recorded_candidates = [dict(candidate or {}) for candidate in list(record.get("candidates", []) or [])]
    recorded_mask = [bool(value) for value in list(record.get("mask", []) or [])]
    if expected_candidates != recorded_candidates:
        raise ValueError("DecisionRecord strict replay mismatch: candidates differ from runtime request.")
    if expected_mask != recorded_mask:
        raise ValueError("DecisionRecord strict replay mismatch: mask differs from runtime request.")
    chosen_action_id = str(record.get("chosen_action_id", "") or "")
    if chosen_action_id and chosen_action_id not in _record_action_ids(record):
        raise ValueError("DecisionRecord strict replay mismatch: chosen_action_id not in recorded candidates.")


def replay_decision_records(
    snapshot: dict,
    decision_records: Iterable[dict],
    *,
    strict: bool = False,
    event_tail: Iterable[dict] | None = None,
) -> tuple["Game", List[object]]:
    game = prepare_replay(snapshot, list(event_tail or []))
    results: List[object] = []
    for record in list(decision_records or []):
        current = dict(record or {})
        decision_id = str(current.get("decision_id", "") or "")
        if not decision_id:
            raise ValueError("DecisionRecord replay requires decision_id.")
        request = game.decision_queue.get(decision_id)
        if request is None:
            raise ValueError(f"DecisionRecord replay could not find pending decision: {decision_id}")
        if strict:
            _assert_strict_candidate_match(request, current)
        result = _build_result_from_decision_record(request, current)
        apply_result = game.resolve_decision(result)
        if strict and not bool(getattr(apply_result, "ok", False)):
            errors = list(getattr(apply_result, "errors", ()) or ())
            raise ValueError(f"DecisionRecord strict replay failed to apply decision {decision_id}: {errors}")
        results.append(apply_result)
    return game, results
