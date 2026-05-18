from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from ..engine.decision_record import DecisionRecordSchemaValidator
from ..engine.replay_store import ReplayStoreReader


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )


def _scoreboard_values(scoreboard: dict[str, Any]) -> list[int]:
    return [_safe_int(value) for value in scoreboard.values()]


def _runtime_player_scores(game: object) -> list[int]:
    scores: list[int] = []
    for player in list(getattr(game, "players", []) or []):
        getter = getattr(player, "get_score", None)
        value = getter() if callable(getter) else getattr(player, "score", 0)
        scores.append(_safe_int(value))
    return scores


def _event_count(replay_path: Path) -> int:
    with sqlite3.connect(str(replay_path)) as conn:
        row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    return _safe_int(row[0] if row else 0)


def _phase_timing_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for record in records:
        item = dict(record or {})
        turn_id = _safe_int(item.get("turn_id", 0))
        phase = str(item.get("phase", "") or "UNKNOWN")
        key = (turn_id, phase)
        bucket = buckets.setdefault(
            key,
            {
                "battle_round": turn_id,
                "phase": phase,
                "decision_count": 0,
                "decision_wall_clock_ms": 0,
            },
        )
        bucket["decision_count"] = _safe_int(bucket.get("decision_count", 0)) + 1
        bucket["decision_wall_clock_ms"] = _safe_int(bucket.get("decision_wall_clock_ms", 0)) + _safe_int(
            item.get("wall_clock_ms", 0)
        )
    rows: list[dict[str, Any]] = []
    for (_turn_id, _phase), bucket in sorted(buckets.items(), key=lambda entry: (entry[0][0], entry[0][1])):
        decision_count = _safe_int(bucket.get("decision_count", 0))
        total_ms = _safe_int(bucket.get("decision_wall_clock_ms", 0))
        rows.append(
            {
                **bucket,
                "mean_decision_wall_clock_ms": round(float(total_ms) / float(decision_count), 3)
                if decision_count > 0
                else 0.0,
            }
        )
    return rows


def _record_validation_errors(
    record: dict[str, Any],
    *,
    validator: DecisionRecordSchemaValidator,
) -> list[str]:
    errors = list(validator.validate(record) or [])
    candidates = list(record.get("candidates", []) or [])
    mask = list(record.get("mask", []) or [])
    if len(mask) != len(candidates):
        errors.append(
            f"mask length {len(mask)} does not match candidate length {len(candidates)}"
        )
    if not candidates:
        errors.append("candidate list is empty")
    chosen_action_id = str(record.get("chosen_action_id", "") or "")
    if bool(record.get("valid", True)) and chosen_action_id:
        legal_action_ids: set[str] = set()
        for index, candidate in enumerate(candidates):
            if index < len(mask) and not bool(mask[index]):
                continue
            action_id = str(dict(candidate or {}).get("action_id", "") or "")
            if action_id:
                legal_action_ids.add(action_id)
        if chosen_action_id not in legal_action_ids:
            errors.append("chosen_action_id is not one of the legal masked candidates")
    outcome = record.get("outcome")
    if not isinstance(outcome, dict) or not isinstance(dict(outcome).get("immediate_deltas", None), dict):
        errors.append("outcome.immediate_deltas is missing")
    return errors


def _diagnostic_reasons(result: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    diagnostic_fields = (
        "tool_action_probe_diagnostics",
        "reserve_arrival_diagnostics",
    )
    for field in diagnostic_fields:
        values = list(result.get(field, []) or [])
        if values:
            reasons.append(f"{field}:{len(values)}")
    for trace in list(result.get("llm_adapter_traces", []) or []):
        item = dict(trace or {})
        if str(item.get("error", "") or ""):
            reasons.append("llm_adapter_trace_error")
        elif "legal" in item and not bool(item.get("legal", False)):
            reasons.append("llm_adapter_trace_illegal")
    return reasons


@dataclass(frozen=True)
class CorpusGameValidation:
    game_index: int
    game_id: str
    accepted: bool
    reasons: tuple[str, ...]
    record_count: int
    replay_decision_count: int
    replay_event_count: int
    replay_keyframe_count: int
    elapsed_seconds: float
    scoreboard: dict[str, int]
    vp_delta: int
    phase_timings: tuple[dict[str, Any], ...]
    replay_path: str
    snapshot_path: str
    player1_army: str
    player2_army: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_index": int(self.game_index),
            "game_id": str(self.game_id),
            "accepted": bool(self.accepted),
            "reasons": list(self.reasons),
            "record_count": int(self.record_count),
            "replay_decision_count": int(self.replay_decision_count),
            "replay_event_count": int(self.replay_event_count),
            "replay_keyframe_count": int(self.replay_keyframe_count),
            "elapsed_seconds": float(self.elapsed_seconds),
            "scoreboard": dict(self.scoreboard),
            "vp_delta": int(self.vp_delta),
            "phase_timings": [dict(row) for row in self.phase_timings],
            "replay_path": str(self.replay_path),
            "snapshot_path": str(self.snapshot_path),
            "player1_army": str(self.player1_army),
            "player2_army": str(self.player2_army),
        }


@dataclass(frozen=True)
class CorpusBatchValidation:
    generated_at_utc: str
    accepted_records: tuple[dict[str, Any], ...]
    games: tuple[CorpusGameValidation, ...]
    rejection_counts: dict[str, int]

    @property
    def accepted_game_count(self) -> int:
        return sum(1 for game in self.games if game.accepted)

    @property
    def rejected_game_count(self) -> int:
        return sum(1 for game in self.games if not game.accepted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at_utc": str(self.generated_at_utc),
            "accepted_game_count": int(self.accepted_game_count),
            "rejected_game_count": int(self.rejected_game_count),
            "accepted_record_count": int(len(self.accepted_records)),
            "rejection_counts": {str(key): int(value) for key, value in sorted(self.rejection_counts.items())},
            "games": [game.to_dict() for game in self.games],
        }


def _validate_replay(
    *,
    replay_path: Path,
    expected_scoreboard: dict[str, int],
    expected_record_count: int,
) -> tuple[list[str], int, int, int]:
    reasons: list[str] = []
    if not replay_path.is_file():
        return ([f"missing_replay:{replay_path}"], 0, 0, 0)

    reader = ReplayStoreReader(replay_path)
    replay_decisions = int(reader.decision_count())
    replay_keyframes = int(reader.keyframe_count())
    replay_events = _event_count(replay_path)
    if replay_decisions != int(expected_record_count):
        reasons.append(f"replay_decision_count_mismatch:{replay_decisions}!={expected_record_count}")

    replayed_game = reader.reconstruct_game_at_decision(replay_decisions, strict=True)
    expected_scores = _scoreboard_values(expected_scoreboard)
    replay_scores = _runtime_player_scores(replayed_game)
    if expected_scores and replay_scores != expected_scores:
        reasons.append(f"replay_score_mismatch:{replay_scores}!={expected_scores}")
    return reasons, replay_decisions, replay_events, replay_keyframes


def validate_self_play_corpus_batch(
    *,
    records: Iterable[dict[str, Any]],
    report: dict[str, Any],
    reject_engine_diagnostics: bool = True,
    require_replay: bool = True,
) -> CorpusBatchValidation:
    record_list = [dict(record or {}) for record in records]
    records_by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in record_list:
        records_by_game[str(record.get("game_id", "") or "")].append(record)

    validator = DecisionRecordSchemaValidator()
    game_validations: list[CorpusGameValidation] = []
    accepted_records: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    player1_army = str(report.get("player1_army", "") or "")
    player2_army = str(report.get("player2_army", "") or "")

    for raw_game in list(report.get("games", []) or []):
        game_entry = dict(raw_game or {})
        result = dict(game_entry.get("result", {}) or {})
        game_id = str(result.get("game_id", "") or "")
        game_records = list(records_by_game.get(game_id, []) or [])
        reasons: list[str] = []
        if not game_id:
            reasons.append("missing_game_id")
        if not game_records:
            reasons.append("missing_records")

        if bool(reject_engine_diagnostics):
            reasons.extend(_diagnostic_reasons(result))

        record_error_count = 0
        for record in game_records:
            record_errors = _record_validation_errors(record, validator=validator)
            if record_errors:
                record_error_count += len(record_errors)
        if record_error_count:
            reasons.append(f"decision_record_validation_errors:{record_error_count}")

        replay_decisions = 0
        replay_events = 0
        replay_keyframes = 0
        if bool(require_replay):
            replay_path = Path(str(result.get("replay_path", "") or ""))
            try:
                replay_reasons, replay_decisions, replay_events, replay_keyframes = _validate_replay(
                    replay_path=replay_path,
                    expected_scoreboard={
                        str(key): _safe_int(value)
                        for key, value in dict(result.get("scoreboard", {}) or {}).items()
                    },
                    expected_record_count=len(game_records),
                )
                reasons.extend(replay_reasons)
            except (OSError, sqlite3.Error, RuntimeError, ValueError, KeyError, TypeError) as exc:
                reasons.append(f"replay_validation_error:{type(exc).__name__}")

        scoreboard = {
            str(key): _safe_int(value)
            for key, value in dict(result.get("scoreboard", {}) or {}).items()
        }
        score_values = list(scoreboard.values())
        vp_delta = int(score_values[0] - score_values[1]) if len(score_values) >= 2 else 0
        accepted = not reasons
        if accepted:
            accepted_records.extend(game_records)
        else:
            for reason in reasons:
                rejection_counts[reason] += 1
        game_validations.append(
            CorpusGameValidation(
                game_index=_safe_int(game_entry.get("game_index", 0)),
                game_id=game_id,
                accepted=accepted,
                reasons=tuple(reasons),
                record_count=len(game_records),
                replay_decision_count=int(replay_decisions),
                replay_event_count=int(replay_events),
                replay_keyframe_count=int(replay_keyframes),
                elapsed_seconds=_safe_float(game_entry.get("elapsed_seconds", 0.0)),
                scoreboard=scoreboard,
                vp_delta=vp_delta,
                phase_timings=tuple(_phase_timing_rows(game_records)),
                replay_path=str(result.get("replay_path", "") or ""),
                snapshot_path=str(result.get("snapshot_path", "") or ""),
                player1_army=player1_army,
                player2_army=player2_army,
            )
        )

    accepted_game_ids = {game.game_id for game in game_validations if game.accepted}
    accepted_records = [
        record for record in accepted_records if str(record.get("game_id", "") or "") in accepted_game_ids
    ]
    return CorpusBatchValidation(
        generated_at_utc=_utc_timestamp(),
        accepted_records=tuple(accepted_records),
        games=tuple(game_validations),
        rejection_counts={str(key): int(value) for key, value in rejection_counts.items()},
    )


def build_corpus_manifest(
    *,
    source_tag: str,
    label_source: str,
    records_path: Path,
    training_manifest_path: Path,
    batches: Iterable[dict[str, Any]],
    games: Iterable[CorpusGameValidation],
    decision_record_count: int,
) -> dict[str, Any]:
    game_rows = [game.to_dict() for game in games]
    rejection_counts: Counter[str] = Counter()
    phase_buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for game in games:
        if not game.accepted:
            for reason in game.reasons:
                rejection_counts[str(reason)] += 1
            continue
        for row in game.phase_timings:
            item = dict(row or {})
            key = (_safe_int(item.get("battle_round", 0)), str(item.get("phase", "") or "UNKNOWN"))
            bucket = phase_buckets.setdefault(
                key,
                {
                    "battle_round": key[0],
                    "phase": key[1],
                    "decision_count": 0,
                    "decision_wall_clock_ms": 0,
                },
            )
            bucket["decision_count"] = _safe_int(bucket.get("decision_count", 0)) + _safe_int(
                item.get("decision_count", 0)
            )
            bucket["decision_wall_clock_ms"] = _safe_int(bucket.get("decision_wall_clock_ms", 0)) + _safe_int(
                item.get("decision_wall_clock_ms", 0)
            )
    phase_timings: list[dict[str, Any]] = []
    for (_turn_id, _phase), bucket in sorted(phase_buckets.items(), key=lambda entry: (entry[0][0], entry[0][1])):
        decision_count = _safe_int(bucket.get("decision_count", 0))
        total_ms = _safe_int(bucket.get("decision_wall_clock_ms", 0))
        phase_timings.append(
            {
                **bucket,
                "mean_decision_wall_clock_ms": round(float(total_ms) / float(decision_count), 3)
                if decision_count > 0
                else 0.0,
            }
        )
    accepted_games = [game for game in game_rows if bool(game.get("accepted", False))]
    rejected_games = [game for game in game_rows if not bool(game.get("accepted", False))]
    return {
        "manifest_version": "training_corpus_v1",
        "generated_at_utc": _utc_timestamp(),
        "source_tag": str(source_tag or ""),
        "label_source": str(label_source or ""),
        "records_path": str(records_path),
        "training_manifest_path": str(training_manifest_path),
        "decision_record_count": int(decision_record_count),
        "accepted_game_count": int(len(accepted_games)),
        "rejected_game_count": int(len(rejected_games)),
        "rejection_counts": {str(key): int(value) for key, value in sorted(rejection_counts.items())},
        "phase_timings": phase_timings,
        "games": game_rows,
        "batches": [dict(batch or {}) for batch in batches],
    }


def save_corpus_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    _json_dump(path, dict(manifest or {}))
    return path


__all__ = [
    "CorpusBatchValidation",
    "CorpusGameValidation",
    "build_corpus_manifest",
    "save_corpus_manifest",
    "validate_self_play_corpus_batch",
]
