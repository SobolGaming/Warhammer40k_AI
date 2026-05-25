from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import sqlite3
from types import MethodType, SimpleNamespace
from typing import Any, Iterator, Optional
import zlib

from .command_kinds import CMD_EXECUTE_SETUP_PHASE, CMD_REQUEST_DECISION, CMD_RESOLVE_DECISION
from .commands import GameCommand
from .decisions import DecisionRequest, DecisionResult
from .game import Game
from .phase import BattleRoundPhases
from .ref_codec import decode_refs

REPLAY_DB_FILENAME = "replay.sqlite3"
REPLAY_FORMAT_ID = "wh40k_replay_sqlite_v1"
REPLAY_FORMAT_VERSION = 1
REPLAY_RECORDING_GROUP = "decision_replay_recording"
DEFAULT_KEYFRAME_INTERVAL = 25
REPLAY_COMPRESSION_LEVEL = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        return [_json_safe(inner) for inner in sorted(value, key=lambda entry: str(entry))]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        enum_value = value.value
        if enum_value is None or isinstance(enum_value, (str, int, float, bool)):
            return enum_value
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    if is_dataclass(value):
        return _json_safe(asdict(value))
    return str(value)


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError):
        return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _pack_json(value: Any) -> bytes:
    return zlib.compress(_canonical_json(value).encode("utf-8"), level=REPLAY_COMPRESSION_LEVEL)


def _pack_canonical_json_text(value: str) -> bytes:
    return zlib.compress(str(value or "").encode("utf-8"), level=REPLAY_COMPRESSION_LEVEL)


def _unpack_json(blob: bytes) -> Any:
    return json.loads(zlib.decompress(blob).decode("utf-8"))


def _request_payload_from_decision_record(record: dict[str, Any]) -> dict[str, Any]:
    candidates = [dict(item or {}) for item in list(record.get("candidates", []) or [])]
    options = []
    for index, candidate in enumerate(candidates):
        action_id = str(candidate.get("action_id", "") or "")
        metadata = dict(candidate.get("metadata", {}) or {})
        label = str(metadata.get("label", "") or action_id or f"Option {index + 1}")
        payload = dict(candidate.get("params", {}) or {})
        if action_id:
            payload.setdefault("action_id", action_id)
        options.append(
            {
                "option_id": action_id or f"option-{index}",
                "label": label,
                "payload": payload,
            }
        )
    context = dict(record.get("request_context", {}) or {})
    prompt = str(context.get("message", "") or context.get("roll_type", "") or record.get("decision_type", "") or "")
    immediate_deltas = dict(dict(record.get("outcome", {}) or {}).get("immediate_deltas", {}) or {})
    actor_player_id = immediate_deltas.get("actor_player_id", None)
    return {
        "decision_id": str(record.get("decision_id", "") or ""),
        "player_id": actor_player_id or None,
        "decision_type": str(record.get("decision_type", "") or ""),
        "prompt": prompt,
        "options": options,
        "context": context,
        "candidates": candidates,
        "mask": list(record.get("mask", []) or []),
        "mask_reasons": list(record.get("mask_reasons", []) or []),
        "created_at": 0.0,
        "timeout_seconds": None,
    }


def _player_controller_kind(game: Game, player_id: str | None) -> str:
    pid = str(player_id or "")
    if not pid:
        return "unknown"
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") != pid:
            continue
        agent_type = str(getattr(player, "agent_type", "") or "").strip().lower()
        if agent_type == "ai" or bool(getattr(player, "is_ai", False)):
            return "ai"
        control = getattr(player, "control", None)
        control_name = str(getattr(control, "name", control) or "").strip().upper()
        if control_name == "REMOTE":
            return "human_remote"
        return "human_local"
    return "unknown"


def _ruleset_payload(game: Game) -> dict[str, Any]:
    bundle = getattr(game, "ruleset_bundle", None)
    if bundle is None:
        return {}
    to_dict = getattr(bundle, "to_dict", None)
    payload = dict(to_dict() or {}) if callable(to_dict) else {}
    rules_bundle_id = str(getattr(bundle, "rules_bundle_id", "") or "")
    if rules_bundle_id:
        payload["rules_bundle_id"] = rules_bundle_id
    return payload


@dataclass(frozen=True)
class ReplayDecisionStep:
    decision_idx: int
    decision_id: str
    turn_id: int
    phase: str
    actor_player_id: str
    controller_kind: str
    decision_type: str
    chosen_option_id: str
    chosen_action_id: str
    valid: bool
    wall_clock_ms: int
    time_budget_ms: int | None
    event_start_id: int | None
    event_end_id: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_idx": int(self.decision_idx),
            "decision_id": str(self.decision_id),
            "turn_id": int(self.turn_id),
            "phase": str(self.phase),
            "actor_player_id": str(self.actor_player_id),
            "controller_kind": str(self.controller_kind),
            "decision_type": str(self.decision_type),
            "chosen_option_id": str(self.chosen_option_id),
            "chosen_action_id": str(self.chosen_action_id),
            "valid": bool(self.valid),
            "wall_clock_ms": int(self.wall_clock_ms),
            "time_budget_ms": self.time_budget_ms,
            "event_start_id": self.event_start_id,
            "event_end_id": self.event_end_id,
        }


class ReplayStoreRecorder:
    def __init__(self, db_path: str | Path, *, keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL) -> None:
        self.db_path = Path(db_path)
        self.keyframe_interval = max(1, int(keyframe_interval or DEFAULT_KEYFRAME_INTERVAL))
        self.last_event_id = 0
        self.last_decision_idx = 0
        self._pending_keyframes: dict[str, int] = {}
        self._pending_command_events: set[str] = set()
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()
        self._refresh_offsets()

    def _open_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self._conn is None:
            self._conn = self._open_connection()
        conn = self._conn
        try:
            yield conn
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise

    def close(self) -> None:
        conn = self._conn
        self._conn = None
        if conn is None:
            return
        conn.commit()
        conn.close()

    def __del__(self) -> None:
        try:
            self.close()
        except sqlite3.Error:
            pass

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_steps (
                    decision_idx INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT NOT NULL UNIQUE,
                    turn_id INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    actor_player_id TEXT NOT NULL,
                    controller_kind TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    chosen_option_id TEXT NOT NULL,
                    chosen_action_id TEXT NOT NULL,
                    valid INTEGER NOT NULL,
                    wall_clock_ms INTEGER NOT NULL,
                    time_budget_ms INTEGER,
                    event_start_id INTEGER,
                    event_end_id INTEGER,
                    request_blob BLOB,
                    decision_record_blob BLOB NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor_id TEXT,
                    payload_blob BLOB NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS keyframes (
                    keyframe_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_idx INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    snapshot_blob BLOB NOT NULL,
                    snapshot_hash TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_steps_turn_phase ON decision_steps(turn_id, phase)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_keyframes_decision_idx ON keyframes(decision_idx)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
            columns = {str(row["name"]) for row in list(conn.execute("PRAGMA table_info(decision_steps)"))}
            if "request_blob" not in columns:
                conn.execute("ALTER TABLE decision_steps ADD COLUMN request_blob BLOB")

    def _get_meta(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = list(conn.execute("SELECT key, value_json FROM meta"))
        meta: dict[str, Any] = {}
        for row in rows:
            meta[str(row["key"])] = json.loads(str(row["value_json"]))
        return meta

    def _set_meta(self, values: dict[str, Any]) -> None:
        if not values:
            return
        with self._connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO meta(key, value_json)
                    VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                    """,
                    (str(key), _canonical_json(value)),
                )

    def _refresh_offsets(self) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(event_id) AS max_event_id FROM events").fetchone()
            self.last_event_id = int(row["max_event_id"] or 0) if row is not None else 0
            row = conn.execute("SELECT MAX(decision_idx) AS max_decision_idx FROM decision_steps").fetchone()
            self.last_decision_idx = int(row["max_decision_idx"] or 0) if row is not None else 0

    def initialize_for_game(self, game: Game, *, session_id: str | None = None, label: str | None = None) -> None:
        if game is None:
            raise ValueError("Game is required for replay initialization.")
        meta = self._get_meta()
        if "format_id" not in meta:
            self._set_meta(
                {
                    "format_id": REPLAY_FORMAT_ID,
                    "format_version": int(REPLAY_FORMAT_VERSION),
                    "created_at": _utc_now(),
                }
            )
        self._set_meta(
            {
                "updated_at": _utc_now(),
                "session_id": str(session_id or ""),
                "label": str(label or ""),
                "ruleset": _ruleset_payload(game),
                "keyframe_interval": int(self.keyframe_interval),
            }
        )
        self._capture_new_events(game)
        if self.keyframe_count() == 0:
            self._write_keyframe(game, decision_idx=0, event_id=self.last_event_id)

    def _capture_new_events(self, game: Game) -> tuple[int | None, int | None, list[dict[str, Any]]]:
        event_log = getattr(game, "event_log", None)
        if event_log is None:
            return None, None, []
        events = list(event_log.serialize_events(since_event_id=self.last_event_id) or [])
        if not events:
            return None, None, []
        events.sort(key=lambda entry: int(entry.get("event_id", 0) or 0))
        with self._connect() as conn:
            for entry in events:
                event_id = int(entry.get("event_id", 0) or 0)
                event_type = str(entry.get("type", entry.get("event_type", "")) or "")
                actor_id = entry.get("actor_id", None)
                payload_blob = _pack_json(dict(entry.get("payload", {}) or {}))
                conn.execute(
                    """
                    INSERT OR IGNORE INTO events(event_id, event_type, actor_id, payload_blob)
                    VALUES(?, ?, ?, ?)
                    """,
                    (event_id, event_type, actor_id, payload_blob),
                )
        start_id = int(events[0].get("event_id", 0) or 0)
        end_id = int(events[-1].get("event_id", 0) or 0)
        self.last_event_id = max(self.last_event_id, end_id)
        return start_id, end_id, [dict(entry or {}) for entry in events]

    def _find_record_for_decision(self, game: Game, decision_id: str) -> dict[str, Any]:
        records = list(getattr(getattr(game, "decision_record_store", None), "records", []) or [])
        for record in reversed(records):
            if str(record.get("decision_id", "") or "") == str(decision_id or ""):
                return dict(record)
        raise ValueError(f"DecisionRecord not found for decision_id={decision_id!r}.")

    def _write_keyframe(self, game: Game, *, decision_idx: int, event_id: int) -> bool:
        try:
            snapshot = game.save_snapshot()
        except RuntimeError:
            # Snapshot serialization is gated to battle round >= 1.
            return False
        snapshot_json = _canonical_json(snapshot)
        snapshot_blob = _pack_canonical_json_text(snapshot_json)
        snapshot_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO keyframes(decision_idx, event_id, snapshot_blob, snapshot_hash)
                VALUES(?, ?, ?, ?)
                """,
                (int(decision_idx), int(event_id), snapshot_blob, snapshot_hash),
            )
        return True

    def _update_decision_step_event_end(self, decision_id: str, event_end_id: int | None) -> None:
        if not decision_id or event_end_id is None:
            return
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE decision_steps
                SET event_end_id = CASE
                    WHEN event_end_id IS NULL OR event_end_id < ? THEN ?
                    ELSE event_end_id
                END
                WHERE decision_id = ?
                """,
                (int(event_end_id), int(event_end_id), str(decision_id)),
            )

    def has_decision_step(self, decision_id: str) -> bool:
        if not decision_id:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM decision_steps WHERE decision_id = ? LIMIT 1",
                (str(decision_id),),
            ).fetchone()
        return row is not None

    def record_decision_request(self, game: Game, request: DecisionRequest) -> int:
        if game is None or request is None:
            return 0
        decision_id = str(getattr(request, "decision_id", "") or "")
        if not decision_id:
            return 0
        event_start_id, event_end_id, events = self._capture_new_events(game)
        request_payload = None
        for entry in list(events or []):
            event_type = str(entry.get("type", entry.get("event_type", "")) or "")
            if event_type != "decision_requested":
                continue
            payload = dict(entry.get("payload", {}) or {})
            if str(payload.get("decision_id", "") or "") == decision_id:
                request_payload = payload
                break
        if request_payload is None:
            request_payload = dict(getattr(request, "to_dict", lambda: {})() or {})
        request_blob = _pack_json(request_payload)
        actor_player_id = str(getattr(request, "player_id", None) or "")
        controller_kind = _player_controller_kind(game, actor_player_id)
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "")
        placeholder_candidates = []
        for candidate in list(getattr(request, "candidates", []) or []):
            if isinstance(candidate, dict):
                placeholder_candidates.append(dict(candidate))
                continue
            placeholder_candidates.append(dict(getattr(candidate, "to_dict", lambda: {})() or {}))
        placeholder_record = {
            "schema_version": 1,
            "decision_id": decision_id,
            "decision_type": str(getattr(request, "decision_type", "") or ""),
            "turn_id": int(getattr(game, "turn", 0) or 0),
            "phase": phase_name,
            "request_context": dict(getattr(request, "context", {}) or {}),
            "candidates": placeholder_candidates,
            "mask": list(getattr(request, "mask", []) or []),
            "chosen_action_id": "",
            "valid": True,
            "outcome": {},
        }
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_idx FROM decision_steps WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO decision_steps(
                        decision_id,
                        turn_id,
                        phase,
                        actor_player_id,
                        controller_kind,
                        decision_type,
                        chosen_option_id,
                        chosen_action_id,
                        valid,
                        wall_clock_ms,
                        time_budget_ms,
                        event_start_id,
                        event_end_id,
                        request_blob,
                        decision_record_blob
                    )
                    VALUES(?, ?, ?, ?, ?, ?, '', '', 1, 0, NULL, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        int(getattr(game, "turn", 0) or 0),
                        phase_name,
                        actor_player_id,
                        controller_kind,
                        str(getattr(request, "decision_type", "") or ""),
                        int(event_start_id) if event_start_id is not None else None,
                        int(event_end_id) if event_end_id is not None else None,
                        request_blob,
                        _pack_json(placeholder_record),
                    ),
                )
                row = conn.execute(
                    "SELECT decision_idx FROM decision_steps WHERE decision_id = ?",
                    (decision_id,),
                ).fetchone()
            else:
                conn.execute(
                    """
                    UPDATE decision_steps
                    SET
                        request_blob = CASE
                            WHEN request_blob IS NULL THEN ?
                            ELSE request_blob
                        END,
                        event_start_id = CASE
                            WHEN event_start_id IS NULL THEN ?
                            WHEN ? IS NULL THEN event_start_id
                            WHEN ? < event_start_id THEN ?
                            ELSE event_start_id
                        END,
                        event_end_id = CASE
                            WHEN event_end_id IS NULL THEN ?
                            WHEN ? IS NULL THEN event_end_id
                            WHEN ? > event_end_id THEN ?
                            ELSE event_end_id
                        END
                    WHERE decision_id = ?
                    """,
                    (
                        request_blob,
                        int(event_start_id) if event_start_id is not None else None,
                        int(event_start_id) if event_start_id is not None else None,
                        int(event_start_id) if event_start_id is not None else None,
                        int(event_start_id) if event_start_id is not None else None,
                        int(event_end_id) if event_end_id is not None else None,
                        int(event_end_id) if event_end_id is not None else None,
                        int(event_end_id) if event_end_id is not None else None,
                        int(event_end_id) if event_end_id is not None else None,
                        decision_id,
                    ),
                )
        decision_idx = int(row["decision_idx"] or 0) if row is not None else 0
        self.last_decision_idx = max(self.last_decision_idx, decision_idx)
        return decision_idx

    def record_decision_record(self, game: Game, record: dict[str, Any]) -> int:
        if game is None:
            raise ValueError("Game is required for replay recording.")
        if not isinstance(record, dict):
            raise ValueError("Decision record is required for replay recording.")
        decision_id = str(record.get("decision_id", "") or "")
        if not decision_id:
            return 0
        immediate_deltas = dict(dict(record.get("outcome", {}) or {}).get("immediate_deltas", {}) or {})
        actor_player_id = str(immediate_deltas.get("actor_player_id", "") or "")
        controller_kind = _player_controller_kind(game, actor_player_id)
        request_payload = _request_payload_from_decision_record(record)
        request_blob = _pack_json(request_payload)
        decision_record_blob = _pack_json(record)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_idx FROM decision_steps WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            time_budget_ms = (
                int(record.get("time_budget_ms", 0) or 0)
                if record.get("time_budget_ms", None) is not None
                else None
            )
            chosen_action_id = str(record.get("chosen_action_id", "") or "")
            if row is None:
                conn.execute(
                    """
                    INSERT INTO decision_steps(
                        decision_id,
                        turn_id,
                        phase,
                        actor_player_id,
                        controller_kind,
                        decision_type,
                        chosen_option_id,
                        chosen_action_id,
                        valid,
                        wall_clock_ms,
                        time_budget_ms,
                        event_start_id,
                        event_end_id,
                        request_blob,
                        decision_record_blob
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                    """,
                    (
                        decision_id,
                        int(record.get("turn_id", 0) or 0),
                        str(record.get("phase", "") or ""),
                        actor_player_id,
                        controller_kind,
                        str(record.get("decision_type", "") or ""),
                        "",
                        chosen_action_id,
                        1 if bool(record.get("valid", True)) else 0,
                        int(record.get("wall_clock_ms", 0) or 0),
                        time_budget_ms,
                        request_blob,
                        decision_record_blob,
                    ),
                )
                row = conn.execute(
                    "SELECT decision_idx FROM decision_steps WHERE decision_id = ?",
                    (decision_id,),
                ).fetchone()
            else:
                conn.execute(
                    """
                    UPDATE decision_steps
                    SET
                        decision_record_blob = ?,
                        chosen_action_id = CASE
                            WHEN ? != '' THEN ?
                            ELSE chosen_action_id
                        END,
                        valid = ?,
                        wall_clock_ms = CASE
                            WHEN ? > wall_clock_ms THEN ?
                            ELSE wall_clock_ms
                        END,
                        time_budget_ms = COALESCE(time_budget_ms, ?),
                        request_blob = CASE
                            WHEN request_blob IS NULL THEN ?
                            ELSE request_blob
                        END
                    WHERE decision_id = ?
                    """,
                    (
                        decision_record_blob,
                        chosen_action_id,
                        chosen_action_id,
                        1 if bool(record.get("valid", True)) else 0,
                        int(record.get("wall_clock_ms", 0) or 0),
                        int(record.get("wall_clock_ms", 0) or 0),
                        time_budget_ms,
                        request_blob,
                        decision_id,
                    ),
                )
        decision_idx = int(row["decision_idx"] or 0) if row is not None else 0
        self.last_decision_idx = max(self.last_decision_idx, decision_idx)
        return decision_idx

    def flush_runtime_tail(self, game: Game, *, write_keyframe: bool = False) -> None:
        if game is None:
            return
        self._capture_new_events(game)
        if bool(write_keyframe):
            decision_idx = int(self.last_decision_idx or 0)
            latest_keyframe = None
            with self._connect() as conn:
                latest_keyframe = conn.execute(
                    """
                    SELECT decision_idx, event_id
                    FROM keyframes
                    ORDER BY keyframe_id DESC
                    LIMIT 1
                    """
                ).fetchone()
            latest_decision_idx = int(latest_keyframe["decision_idx"] or 0) if latest_keyframe is not None else None
            latest_event_id = int(latest_keyframe["event_id"] or 0) if latest_keyframe is not None else None
            if latest_decision_idx != decision_idx or latest_event_id != int(self.last_event_id):
                self._write_keyframe(game, decision_idx=decision_idx, event_id=int(self.last_event_id))
        self._set_meta(
            {
                "updated_at": _utc_now(),
                "last_decision_idx": int(self.last_decision_idx),
                "last_event_id": int(self.last_event_id),
            }
        )

    def record_resolution(
        self,
        game: Game,
        request: DecisionRequest,
        result: DecisionResult,
        *,
        defer_keyframe: bool = False,
    ) -> int:
        if game is None:
            raise ValueError("Game is required for replay recording.")
        if request is None or result is None:
            raise ValueError("Request and result are required for replay recording.")
        record = self._find_record_for_decision(game, str(getattr(request, "decision_id", "") or ""))
        event_start_id, event_end_id, events = self._capture_new_events(game)
        request_payload: dict[str, Any] | None = None
        for entry in list(events or []):
            event_type = str(entry.get("type", entry.get("event_type", "")) or "")
            if event_type != "decision_requested":
                continue
            payload = dict(entry.get("payload", {}) or {})
            if str(payload.get("decision_id", "") or "") == str(getattr(request, "decision_id", "") or ""):
                request_payload = payload
                break
        if request_payload is None:
            request_payload = dict(getattr(request, "to_dict", lambda: {})() or {})
        actor_player_id = str(
            getattr(result, "player_id", None)
            or getattr(request, "player_id", None)
            or str(record.get("player_id", "") or "")
        )
        controller_kind = _player_controller_kind(game, actor_player_id)
        decision_id = str(record.get("decision_id", "") or "")
        decision_record_blob = _pack_json(record)
        request_blob = _pack_json(request_payload) if request_payload is not None else None
        time_budget_ms = (
            int(record.get("time_budget_ms", 0) or 0)
            if record.get("time_budget_ms", None) is not None
            else None
        )
        event_start_value = int(event_start_id) if event_start_id is not None else None
        event_end_value = int(event_end_id) if event_end_id is not None else None
        chosen_option_id = str(getattr(result, "option_id", "") or "")
        chosen_action_id = str(record.get("chosen_action_id", "") or "")
        wall_clock_ms = int(record.get("wall_clock_ms", 0) or 0)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_idx FROM decision_steps WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO decision_steps(
                        decision_id,
                        turn_id,
                        phase,
                        actor_player_id,
                        controller_kind,
                        decision_type,
                        chosen_option_id,
                        chosen_action_id,
                        valid,
                        wall_clock_ms,
                        time_budget_ms,
                        event_start_id,
                        event_end_id,
                        request_blob,
                        decision_record_blob
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        int(record.get("turn_id", 0) or 0),
                        str(record.get("phase", "") or ""),
                        actor_player_id,
                        controller_kind,
                        str(record.get("decision_type", "") or ""),
                        chosen_option_id,
                        chosen_action_id,
                        1 if bool(record.get("valid", True)) else 0,
                        wall_clock_ms,
                        time_budget_ms,
                        event_start_value,
                        event_end_value,
                        request_blob,
                        decision_record_blob,
                    ),
                )
                row = conn.execute(
                    "SELECT decision_idx FROM decision_steps WHERE decision_id = ?",
                    (decision_id,),
                ).fetchone()
            else:
                conn.execute(
                    """
                    UPDATE decision_steps
                    SET
                        event_start_id = CASE
                            WHEN event_start_id IS NULL THEN ?
                            WHEN ? IS NULL THEN event_start_id
                            WHEN ? < event_start_id THEN ?
                            ELSE event_start_id
                        END,
                        event_end_id = CASE
                            WHEN event_end_id IS NULL THEN ?
                            WHEN ? IS NULL THEN event_end_id
                            WHEN ? > event_end_id THEN ?
                            ELSE event_end_id
                        END,
                        request_blob = CASE
                            WHEN ? IS NOT NULL THEN ?
                            ELSE request_blob
                        END,
                        decision_record_blob = ?,
                        chosen_option_id = CASE
                            WHEN ? != '' THEN ?
                            ELSE chosen_option_id
                        END,
                        chosen_action_id = CASE
                            WHEN ? != '' THEN ?
                            ELSE chosen_action_id
                        END,
                        valid = ?,
                        wall_clock_ms = CASE
                            WHEN ? > wall_clock_ms THEN ?
                            ELSE wall_clock_ms
                        END,
                        time_budget_ms = COALESCE(time_budget_ms, ?)
                    WHERE decision_id = ?
                    """,
                    (
                        event_start_value,
                        event_start_value,
                        event_start_value,
                        event_start_value,
                        event_end_value,
                        event_end_value,
                        event_end_value,
                        event_end_value,
                        request_blob,
                        request_blob,
                        decision_record_blob,
                        chosen_option_id,
                        chosen_option_id,
                        chosen_action_id,
                        chosen_action_id,
                        1 if bool(record.get("valid", True)) else 0,
                        wall_clock_ms,
                        wall_clock_ms,
                        time_budget_ms,
                        decision_id,
                    ),
                )
            decision_idx = int(row["decision_idx"] or 0) if row is not None else 0
        if decision_idx <= 0:
            raise RuntimeError("Failed to persist replay decision step.")
        self.last_decision_idx = max(self.last_decision_idx, decision_idx)
        if bool(getattr(game, "in_command_context", lambda: False)()):
            self._pending_command_events.add(str(record.get("decision_id", "") or ""))
        if (decision_idx % self.keyframe_interval) == 0:
            decision_id = str(record.get("decision_id", "") or getattr(request, "decision_id", "") or "")
            if defer_keyframe and decision_id:
                self._pending_keyframes[decision_id] = int(decision_idx)
            else:
                self._write_keyframe(game, decision_idx=decision_idx, event_id=int(self.last_event_id))
        return decision_idx

    def finalize_resolution(self, game: Game, request: DecisionRequest | None) -> None:
        if game is None or request is None:
            return
        decision_id = str(getattr(request, "decision_id", "") or "")
        if not decision_id:
            return
        decision_idx = self._pending_keyframes.pop(decision_id, None)
        if decision_idx is None:
            return
        self._write_keyframe(game, decision_idx=int(decision_idx), event_id=int(self.last_event_id))
        self._set_meta({"updated_at": _utc_now()})

    def record_post_command(self, game: Game, command: GameCommand | None, result: Any | None) -> None:
        if game is None or command is None:
            return
        _event_start_id, event_end_id, events = self._capture_new_events(game)
        if str(getattr(command, "kind", "") or "") != CMD_RESOLVE_DECISION:
            return
        payload = dict(getattr(command, "payload", {}) or {})
        decision_id = str(payload.get("decision_id", "") or "")
        if not decision_id:
            return
        if not bool(getattr(result, "ok", False)):
            self._pending_command_events.discard(decision_id)
            return
        if decision_id not in self._pending_command_events:
            return
        self._pending_command_events.discard(decision_id)
        command_id = str(getattr(command, "command_id", "") or "")
        command_event_id = None
        for entry in list(events or []):
            payload = dict(entry.get("payload", {}) or {})
            if str(payload.get("command_id", "") or "") != command_id:
                continue
            if str(entry.get("type", entry.get("event_type", "")) or "") not in {"command_applied", "command_rejected"}:
                continue
            command_event_id = int(entry.get("event_id", 0) or 0)
            break
        if command_event_id is None:
            command_event_id = event_end_id
        self._update_decision_step_event_end(decision_id, command_event_id)

    def decision_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(decision_idx) AS c FROM decision_steps").fetchone()
        return int(row["c"] or 0) if row is not None else 0

    def decision_row_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM decision_steps").fetchone()
        return int(row["c"] or 0) if row is not None else 0

    def keyframe_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM keyframes").fetchone()
        return int(row["c"] or 0) if row is not None else 0


class ReplayStoreReader:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Replay store not found: {self.db_path}")
        self._validate_format()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _meta(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = list(conn.execute("SELECT key, value_json FROM meta"))
        meta: dict[str, Any] = {}
        for row in rows:
            meta[str(row["key"])] = json.loads(str(row["value_json"]))
        return meta

    def _validate_format(self) -> None:
        meta = self._meta()
        format_id = str(meta.get("format_id", "") or "")
        if format_id and format_id != REPLAY_FORMAT_ID:
            raise ValueError(f"Unsupported replay format: {format_id}")
        format_version = int(meta.get("format_version", 0) or 0)
        if format_version and format_version != REPLAY_FORMAT_VERSION:
            raise ValueError(f"Unsupported replay format version: {format_version}")

    def metadata(self) -> dict[str, Any]:
        return self._meta()

    def decision_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(decision_idx) AS c FROM decision_steps").fetchone()
        return int(row["c"] or 0) if row is not None else 0

    def decision_row_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM decision_steps").fetchone()
        return int(row["c"] or 0) if row is not None else 0

    def keyframe_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM keyframes").fetchone()
        return int(row["c"] or 0) if row is not None else 0

    def list_steps(self, *, offset: int = 0, limit: int = 100) -> list[ReplayDecisionStep]:
        with self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT
                        decision_idx,
                        decision_id,
                        turn_id,
                        phase,
                        actor_player_id,
                        controller_kind,
                        decision_type,
                        chosen_option_id,
                        chosen_action_id,
                        valid,
                        wall_clock_ms,
                        time_budget_ms,
                        event_start_id,
                        event_end_id
                    FROM decision_steps
                    ORDER BY decision_idx ASC
                    LIMIT ? OFFSET ?
                    """,
                    (max(1, int(limit or 1)), max(0, int(offset or 0))),
                )
            )
        steps: list[ReplayDecisionStep] = []
        for row in rows:
            steps.append(
                ReplayDecisionStep(
                    decision_idx=int(row["decision_idx"]),
                    decision_id=str(row["decision_id"] or ""),
                    turn_id=int(row["turn_id"] or 0),
                    phase=str(row["phase"] or ""),
                    actor_player_id=str(row["actor_player_id"] or ""),
                    controller_kind=str(row["controller_kind"] or ""),
                    decision_type=str(row["decision_type"] or ""),
                    chosen_option_id=str(row["chosen_option_id"] or ""),
                    chosen_action_id=str(row["chosen_action_id"] or ""),
                    valid=bool(int(row["valid"] or 0)),
                    wall_clock_ms=int(row["wall_clock_ms"] or 0),
                    time_budget_ms=(int(row["time_budget_ms"]) if row["time_budget_ms"] is not None else None),
                    event_start_id=(int(row["event_start_id"]) if row["event_start_id"] is not None else None),
                    event_end_id=(int(row["event_end_id"]) if row["event_end_id"] is not None else None),
                )
            )
        return steps

    def get_step(self, decision_idx: int) -> ReplayDecisionStep:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    decision_idx,
                    decision_id,
                    turn_id,
                    phase,
                    actor_player_id,
                    controller_kind,
                    decision_type,
                    chosen_option_id,
                    chosen_action_id,
                    valid,
                    wall_clock_ms,
                    time_budget_ms,
                    event_start_id,
                    event_end_id
                FROM decision_steps
                WHERE decision_idx = ?
                """,
                (int(decision_idx),),
            ).fetchone()
        if row is None:
            raise IndexError(f"Decision step not found: {decision_idx}")
        return ReplayDecisionStep(
            decision_idx=int(row["decision_idx"]),
            decision_id=str(row["decision_id"] or ""),
            turn_id=int(row["turn_id"] or 0),
            phase=str(row["phase"] or ""),
            actor_player_id=str(row["actor_player_id"] or ""),
            controller_kind=str(row["controller_kind"] or ""),
            decision_type=str(row["decision_type"] or ""),
            chosen_option_id=str(row["chosen_option_id"] or ""),
            chosen_action_id=str(row["chosen_action_id"] or ""),
            valid=bool(int(row["valid"] or 0)),
            wall_clock_ms=int(row["wall_clock_ms"] or 0),
            time_budget_ms=(int(row["time_budget_ms"]) if row["time_budget_ms"] is not None else None),
            event_start_id=(int(row["event_start_id"]) if row["event_start_id"] is not None else None),
            event_end_id=(int(row["event_end_id"]) if row["event_end_id"] is not None else None),
        )

    def get_decision_record(self, decision_idx: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_record_blob FROM decision_steps WHERE decision_idx = ?",
                (int(decision_idx),),
            ).fetchone()
        if row is None:
            raise IndexError(f"Decision step not found: {decision_idx}")
        return dict(_unpack_json(bytes(row["decision_record_blob"])))

    def get_request_payload(self, decision_idx: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT request_blob FROM decision_steps WHERE decision_idx = ?",
                (int(decision_idx),),
            ).fetchone()
        if row is None:
            raise IndexError(f"Decision step not found: {decision_idx}")
        blob = row["request_blob"]
        if blob is None:
            return {}
        return dict(_unpack_json(bytes(blob)))

    def get_events_for_decision(self, decision_idx: int) -> list[dict[str, Any]]:
        step = self.get_step(decision_idx)
        if step.event_start_id is None or step.event_end_id is None:
            return []
        with self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT event_id, event_type, actor_id, payload_blob
                    FROM events
                    WHERE event_id >= ? AND event_id <= ?
                    ORDER BY event_id ASC
                    """,
                    (int(step.event_start_id), int(step.event_end_id)),
                )
            )
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "event_id": int(row["event_id"]),
                    "type": str(row["event_type"] or ""),
                    "actor_id": row["actor_id"],
                    "payload": dict(_unpack_json(bytes(row["payload_blob"]))),
                }
            )
        return events

    def get_events_until_event_id(self, event_id: int) -> list[dict[str, Any]]:
        end_event_id = int(event_id)
        if end_event_id <= 0:
            return []
        with self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT event_id, event_type, actor_id, payload_blob
                    FROM events
                    WHERE event_id <= ?
                    ORDER BY event_id ASC
                    """,
                    (end_event_id,),
                )
            )
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "event_id": int(row["event_id"]),
                    "type": str(row["event_type"] or ""),
                    "actor_id": row["actor_id"],
                    "payload": dict(_unpack_json(bytes(row["payload_blob"]))),
                }
            )
        return events

    def _nearest_keyframe(self, decision_idx: int) -> sqlite3.Row:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT keyframe_id, decision_idx, event_id, snapshot_blob
                FROM keyframes
                WHERE decision_idx <= ?
                ORDER BY decision_idx DESC, keyframe_id DESC
                LIMIT 1
                """,
                (int(decision_idx),),
            ).fetchone()
        if row is None:
            raise RuntimeError("Replay store is missing keyframes.")
        return row

    def _events_between(self, start_event_id: int, end_event_id: int) -> list[dict[str, Any]]:
        if int(end_event_id) <= int(start_event_id):
            return []
        with self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT event_id, event_type, actor_id, payload_blob
                    FROM events
                    WHERE event_id > ? AND event_id <= ?
                    ORDER BY event_id ASC
                    """,
                    (int(start_event_id), int(end_event_id)),
                )
            )
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "event_id": int(row["event_id"]),
                    "type": str(row["event_type"] or ""),
                    "actor_id": row["actor_id"],
                    "payload": dict(_unpack_json(bytes(row["payload_blob"]))),
                }
            )
        return events

    @staticmethod
    def _prepare_reconstruction_game(snapshot: dict[str, Any]) -> Game:
        game = Game.load_snapshot(snapshot)
        game.auto_resolve_dice_rolls = False
        game._replay_reconstruction_suppress_charge_followups = True
        controller_hub = getattr(game, "decision_controller_hub", None)
        if controller_hub is not None and hasattr(controller_hub, "detach"):
            controller_hub.detach()
        existing_log = getattr(game, "event_log", None)
        if existing_log is not None and hasattr(existing_log, "detach"):
            existing_log.detach()
        game.event_log = None
        return game

    @staticmethod
    def _sync_reconstructed_game_to_step(game: Game, step: ReplayDecisionStep) -> None:
        phase_name = str(getattr(step, "phase", "") or "")
        if not phase_name:
            return
        if phase_name in BattleRoundPhases.__members__:
            game.phase = BattleRoundPhases[phase_name]

    @staticmethod
    def _decode_replay_value(game: Game, value: Any) -> Any:
        registry = getattr(game, "entity_registry", None)
        if registry is None:
            return value
        try:
            return decode_refs(value, registry)
        except KeyError:
            return value

    def _command_from_payload(self, game: Game, payload: dict[str, Any]) -> GameCommand:
        return GameCommand.from_dict(
            {
                "command_id": str(payload.get("command_id", "") or ""),
                "kind": str(payload.get("kind", "") or ""),
                "player_id": payload.get("player_id", None),
                "payload": dict(self._decode_replay_value(game, dict(payload.get("payload", {}) or {})) or {}),
                "metadata": dict(self._decode_replay_value(game, dict(payload.get("metadata", {}) or {})) or {}),
                "created_at": float(payload.get("created_at", 0.0) or 0.0),
            }
        )

    @staticmethod
    def _runtime_unit_id_map(game: Game, record: dict[str, Any]) -> dict[str, str]:
        state = dict(record.get("omniscient_state", {}) or {})
        recorded_units = list(state.get("units", []) or [])
        runtime_units_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for player in list(getattr(game, "players", []) or []):
            army = getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                key = (str(getattr(player, "id", "") or ""), str(getattr(unit, "name", "") or ""))
                runtime_units_by_key.setdefault(key, []).append(ReplayStoreReader._runtime_unit_match_entry(unit))
        recorded_units_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for entry in recorded_units:
            payload = dict(entry or {})
            key = (str(payload.get("owner_player_id", "") or ""), str(payload.get("name", "") or ""))
            recorded_units_by_key.setdefault(key, []).append(ReplayStoreReader._recorded_unit_match_entry(payload))
        unit_id_map: dict[str, str] = {}
        for key, recorded_entries in recorded_units_by_key.items():
            runtime_entries = list(runtime_units_by_key.get(key, []) or [])
            if len(recorded_entries) != len(runtime_entries):
                continue
            if len(recorded_entries) == 1:
                recorded_id = str(recorded_entries[0].get("unit_id", "") or "")
                runtime_id = str(runtime_entries[0].get("unit_id", "") or "")
                if recorded_id and runtime_id:
                    unit_id_map[recorded_id] = runtime_id
                continue
            if not any(ReplayStoreReader._unit_entry_has_disambiguators(entry) for entry in recorded_entries):
                for recorded_entry, runtime_entry in zip(recorded_entries, runtime_entries):
                    recorded_id = str(recorded_entry.get("unit_id", "") or "")
                    runtime_id = str(runtime_entry.get("unit_id", "") or "")
                    if recorded_id and runtime_id:
                        unit_id_map[recorded_id] = runtime_id
                continue
            unmatched = list(runtime_entries)
            for recorded_entry in list(recorded_entries):
                recorded_id = str(recorded_entry.get("unit_id", "") or "")
                if not recorded_id or not unmatched:
                    continue
                best_index = min(
                    range(len(unmatched)),
                    key=lambda idx: ReplayStoreReader._unit_match_score(recorded_entry, unmatched[idx]),
                )
                runtime_entry = unmatched.pop(int(best_index))
                runtime_id = str(runtime_entry.get("unit_id", "") or "")
                if runtime_id:
                    unit_id_map[recorded_id] = runtime_id
        return unit_id_map

    @staticmethod
    def _safe_int(value: Any, default: int = -1) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _position_tuple(value: Any) -> tuple[float, float, float] | None:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        try:
            x = float(value[0])
            y = float(value[1])
            z = float(value[2]) if len(value) > 2 else 0.0
        except (TypeError, ValueError):
            return None
        return (x, y, z)

    @staticmethod
    def _model_alive(model: Any) -> bool:
        alive = getattr(model, "is_alive", True)
        if callable(alive):
            try:
                return bool(alive())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return False
        return bool(alive)

    @staticmethod
    def _runtime_model_position(model: Any) -> tuple[float, float, float] | None:
        getter = getattr(model, "get_location", None)
        if callable(getter):
            location = getter()
            parsed = ReplayStoreReader._position_tuple(location)
            if parsed is not None:
                return parsed
        base = getattr(model, "model_base", None)
        if base is None:
            return None
        try:
            return (
                float(getattr(base, "x", 0.0) or 0.0),
                float(getattr(base, "y", 0.0) or 0.0),
                float(getattr(base, "z", 0.0) or 0.0),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _runtime_unit_position(unit: Any, alive_models: list[Any]) -> tuple[float, float, float] | None:
        explicit = ReplayStoreReader._position_tuple(getattr(unit, "position", None))
        if explicit is not None:
            return explicit
        positions = [
            position
            for position in (ReplayStoreReader._runtime_model_position(model) for model in list(alive_models or []))
            if position is not None
        ]
        if not positions:
            return None
        count = float(len(positions))
        return (
            sum(float(position[0]) for position in positions) / count,
            sum(float(position[1]) for position in positions) / count,
            sum(float(position[2]) for position in positions) / count,
        )

    @staticmethod
    def _runtime_unit_match_entry(unit: Any) -> dict[str, Any]:
        models = list(getattr(unit, "models", []) or [])
        alive_models = [model for model in models if ReplayStoreReader._model_alive(model)]
        return {
            "unit_id": str(getattr(unit, "id", "") or ""),
            "model_count": int(len(models)),
            "alive_model_count": int(len(alive_models)),
            "position": ReplayStoreReader._runtime_unit_position(unit, alive_models),
        }

    @staticmethod
    def _recorded_unit_match_entry(payload: dict[str, Any]) -> dict[str, Any]:
        position = ReplayStoreReader._position_tuple(payload.get("position"))
        model_count = ReplayStoreReader._safe_int(payload.get("model_count"), -1)
        alive_model_count = ReplayStoreReader._safe_int(payload.get("alive_model_count"), model_count)
        return {
            "unit_id": str(payload.get("unit_id", "") or ""),
            "model_count": model_count,
            "alive_model_count": alive_model_count,
            "position": position,
        }

    @staticmethod
    def _unit_entry_has_disambiguators(entry: dict[str, Any]) -> bool:
        return (
            ReplayStoreReader._safe_int(entry.get("model_count"), -1) >= 0
            or ReplayStoreReader._safe_int(entry.get("alive_model_count"), -1) >= 0
            or entry.get("position") is not None
        )

    @staticmethod
    def _unit_match_score(recorded: dict[str, Any], runtime: dict[str, Any]) -> tuple[float, str]:
        score = 0.0
        recorded_count = ReplayStoreReader._safe_int(recorded.get("model_count"), -1)
        runtime_count = ReplayStoreReader._safe_int(runtime.get("model_count"), -1)
        if recorded_count >= 0 and runtime_count >= 0:
            score += float(abs(recorded_count - runtime_count)) * 100000.0
        recorded_alive = ReplayStoreReader._safe_int(recorded.get("alive_model_count"), -1)
        runtime_alive = ReplayStoreReader._safe_int(runtime.get("alive_model_count"), -1)
        if recorded_alive >= 0 and runtime_alive >= 0:
            score += float(abs(recorded_alive - runtime_alive)) * 10000.0
        recorded_pos = recorded.get("position")
        runtime_pos = runtime.get("position")
        if recorded_pos is not None and runtime_pos is not None:
            dx = float(recorded_pos[0]) - float(runtime_pos[0])
            dy = float(recorded_pos[1]) - float(runtime_pos[1])
            dz = float(recorded_pos[2]) - float(runtime_pos[2])
            score += (dx * dx) + (dy * dy) + (dz * dz)
        elif recorded_pos is not None or runtime_pos is not None:
            score += 1000.0
        return (score, str(runtime.get("unit_id", "") or ""))

    @classmethod
    def _collect_ordered_model_ids(cls, value: Any) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        def _visit(current: Any) -> None:
            if isinstance(current, dict):
                for key, inner in current.items():
                    key_name = str(key or "")
                    if key_name.endswith("model_id") and isinstance(inner, str) and inner and inner not in seen:
                        seen.add(inner)
                        ordered.append(inner)
                        continue
                    if key_name.endswith("model_ids") and isinstance(inner, list):
                        for item in inner:
                            if isinstance(item, str) and item and item not in seen:
                                seen.add(item)
                                ordered.append(item)
                        continue
                    _visit(inner)
                return
            if isinstance(current, list):
                for inner in current:
                    _visit(inner)

        _visit(value)
        return ordered

    @staticmethod
    def _request_unit_id(payload: dict[str, Any]) -> str:
        context = dict(payload.get("context", {}) or {})
        unit_id = str(context.get("unit_id", "") or "")
        if unit_id:
            return unit_id
        for option in list(payload.get("options", []) or []):
            option_payload = dict(dict(option or {}).get("payload", {}) or {})
            unit_id = str(option_payload.get("unit_id", "") or "")
            if unit_id:
                return unit_id
        return ""

    @classmethod
    def _runtime_model_id_map(
        cls,
        game: Game,
        payload: dict[str, Any],
        unit_id_map: dict[str, str],
    ) -> dict[str, str]:
        recorded_unit_id = cls._request_unit_id(payload)
        runtime_unit_id = unit_id_map.get(recorded_unit_id, recorded_unit_id)
        if not runtime_unit_id:
            return {}
        registry = getattr(game, "entity_registry", None)
        if registry is None:
            return {}
        runtime_unit = registry.get(runtime_unit_id, kind="unit")
        if runtime_unit is None:
            return {}
        recorded_model_ids = cls._collect_ordered_model_ids(payload)
        runtime_models = list(getattr(runtime_unit, "models", []) or [])
        if len(recorded_model_ids) != len(runtime_models):
            attached_getter = getattr(runtime_unit, "get_attached_unit_models", None)
            attached_models = list(attached_getter() or []) if callable(attached_getter) else []
            if len(recorded_model_ids) == len(attached_models):
                runtime_models = attached_models
        runtime_model_ids = [str(getattr(model, "id", "") or "") for model in runtime_models]
        if not recorded_model_ids or len(recorded_model_ids) != len(runtime_model_ids):
            return {}
        runtime_model_id_set = {model_id for model_id in runtime_model_ids if model_id}
        recorded_model_id_set = {model_id for model_id in recorded_model_ids if model_id}
        if recorded_model_id_set and recorded_model_id_set.issubset(runtime_model_id_set):
            return {}
        if recorded_model_id_set.intersection(runtime_model_id_set):
            unmapped_recorded_ids = [
                model_id for model_id in recorded_model_ids if model_id not in runtime_model_id_set
            ]
            available_runtime_ids = [
                model_id for model_id in runtime_model_ids if model_id not in recorded_model_id_set
            ]
            if len(unmapped_recorded_ids) != len(available_runtime_ids):
                return {}
            return {
                recorded_model_id: runtime_model_id
                for recorded_model_id, runtime_model_id in zip(unmapped_recorded_ids, available_runtime_ids)
                if recorded_model_id and runtime_model_id and recorded_model_id != runtime_model_id
            }
        return {
            recorded_model_id: runtime_model_id
            for recorded_model_id, runtime_model_id in zip(recorded_model_ids, runtime_model_ids)
            if recorded_model_id and runtime_model_id and recorded_model_id != runtime_model_id
        }

    @classmethod
    def _remap_runtime_ids(cls, value: Any, id_map: dict[str, str]) -> Any:
        if not id_map:
            return value
        if isinstance(value, dict):
            if "__ref__" in value:
                ref = dict(value.get("__ref__", {}) or {})
                ref_id = str(ref.get("id", "") or "")
                if ref_id in id_map:
                    ref["id"] = id_map[ref_id]
                return {"__ref__": ref}
            return {str(key): cls._remap_runtime_ids(inner, id_map) for key, inner in value.items()}
        if isinstance(value, list):
            return [cls._remap_runtime_ids(inner, id_map) for inner in value]
        if isinstance(value, str):
            return id_map.get(value, value)
        return value

    @classmethod
    def _request_payload_for_runtime(
        cls,
        game: Game,
        payload: dict[str, Any],
        record: dict[str, Any] | None,
    ) -> dict[str, Any]:
        translated = dict(payload or {})
        if not record:
            return translated
        unit_id_map = cls._runtime_unit_id_map(game, record)
        model_id_map = cls._runtime_model_id_map(game, translated, unit_id_map)
        id_map = dict(unit_id_map)
        id_map.update(model_id_map)
        if not id_map:
            return translated
        return dict(cls._remap_runtime_ids(translated, id_map) or {})

    @classmethod
    def _action_params_for_runtime(
        cls,
        game: Game,
        params: dict[str, Any],
        request_payload: dict[str, Any] | None,
        record: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload_like = {
            "context": dict(dict(request_payload or {}).get("context", {}) or {}),
            "options": [{"payload": dict(params or {})}],
        }
        translated = cls._request_payload_for_runtime(game, payload_like, record)
        options = list(dict(translated or {}).get("options", []) or [])
        if not options:
            return dict(params or {})
        return dict(dict(options[0] or {}).get("payload", {}) or {})

    def _decision_request_from_payload(self, game: Game, payload: dict[str, Any]) -> DecisionRequest:
        request_data = {
            "decision_id": str(payload.get("decision_id", "") or ""),
            "player_id": payload.get("player_id", None),
            "decision_type": str(payload.get("decision_type", "") or ""),
            "prompt": str(payload.get("prompt", "") or ""),
            "options": self._decode_replay_value(game, list(payload.get("options", []) or [])),
            "context": self._decode_replay_value(game, dict(payload.get("context", {}) or {})),
            "candidates": self._decode_replay_value(game, list(payload.get("candidates", []) or [])),
            "mask": list(payload.get("mask", []) or []),
            "mask_reasons": list(payload.get("mask_reasons", []) or []),
            "timeout_seconds": payload.get("timeout_seconds", None),
        }
        return DecisionRequest.from_dict(request_data)

    @staticmethod
    def _recorded_roll_results(record: dict[str, Any]) -> dict[str, Any]:
        outcome = dict(record.get("outcome", {}) or {})
        immediate = dict(outcome.get("immediate_deltas", {}) or {})
        value = immediate.get("value")
        if not isinstance(value, dict):
            return {}
        dice = list(value.get("dice", []) or [])
        if not dice:
            return {}
        return {
            "dice": [dict(entry) for entry in dice if isinstance(entry, dict)],
            "total": int(value.get("total", 0) or 0),
            "reroll_options": list(value.get("reroll_options", []) or []),
        }

    @staticmethod
    def _roll_queue_entry_from_record(payload: dict[str, Any], record: dict[str, Any]) -> dict[str, Any] | None:
        from .decision_kinds import DECISION_REQUEST_DICE_ROLL

        if str(dict(payload or {}).get("decision_type", "") or "") != DECISION_REQUEST_DICE_ROLL:
            return None
        roll_results = ReplayStoreReader._recorded_roll_results(record)
        if not roll_results:
            return None
        ctx = dict(dict(payload or {}).get("context", {}) or {})
        spec = dict(ctx.get("roll_spec", {}) or {})
        return {
            "player_id": dict(payload or {}).get("player_id", None),
            "prompt": str(dict(payload or {}).get("prompt", "") or ""),
            "reason": str(spec.get("reason", "") or ""),
            "roll_type": str(spec.get("roll_type", ctx.get("roll_type", "")) or ""),
            "roll_results": roll_results,
        }

    @staticmethod
    def _recorded_roll_matches_request(entry: dict[str, Any], *, player_id: object, spec: dict, prompt: str | None) -> bool:
        entry_player_id = entry.get("player_id", None)
        if entry_player_id is not None and player_id is not None and str(entry_player_id) != str(player_id):
            return False
        entry_roll_type = str(entry.get("roll_type", "") or "")
        spec_roll_type = str(dict(spec or {}).get("roll_type", "") or "")
        if entry_roll_type and spec_roll_type and entry_roll_type != spec_roll_type:
            return False
        entry_reason = str(entry.get("reason", "") or entry.get("prompt", "") or "")
        request_reason = str(dict(spec or {}).get("reason", "") or prompt or "")
        return not entry_reason or not request_reason or entry_reason == request_reason

    @classmethod
    def _pop_recorded_roll_for_request(
        cls,
        game: Game,
        *,
        player_id: object,
        spec: dict,
        prompt: str | None,
    ) -> dict[str, Any]:
        queue = list(getattr(game, "_replay_recorded_roll_results_queue", []) or [])
        if not queue:
            return {}
        match_index = next(
            (
                idx
                for idx, entry in enumerate(queue)
                if cls._recorded_roll_matches_request(entry, player_id=player_id, spec=spec, prompt=prompt)
            ),
            None,
        )
        if match_index is None:
            match_index = 0
        entry = dict(queue.pop(int(match_index)) or {})
        setattr(game, "_replay_recorded_roll_results_queue", queue)
        return dict(entry.get("roll_results", {}) or {})

    @classmethod
    def _install_replay_dice_request_adapter(cls, game: Game) -> None:
        original_request_dice_roll = getattr(game, "request_dice_roll", None)
        if not callable(original_request_dice_roll):
            return

        def _request_dice_roll_with_replay_results(
            self: Game,
            *,
            player_id: Optional[str],
            spec: dict,
            prompt: Optional[str] = None,
        ) -> DecisionRequest:
            replay_spec = dict(spec or {})
            roll_results = cls._pop_recorded_roll_for_request(
                self,
                player_id=player_id,
                spec=replay_spec,
                prompt=prompt,
            )
            dice = [dict(entry) for entry in list(dict(roll_results or {}).get("dice", []) or []) if isinstance(entry, dict)]
            if dice:
                replay_spec["fixed_dice"] = [
                    int(entry.get("value", 0) or 0)
                    for entry in dice
                    if not bool(entry.get("is_derived", False))
                ]
                replay_spec["fixed_raw_dice"] = [
                    int(entry.get("raw_value", entry.get("value", 0)) or entry.get("value", 0) or 0)
                    for entry in dice
                    if not bool(entry.get("is_derived", False))
                ]
                derived = [dict(entry) for entry in dice if bool(entry.get("is_derived", False))]
                if derived:
                    replay_spec["derived_dice"] = derived
            return original_request_dice_roll(player_id=player_id, spec=replay_spec, prompt=prompt)

        game.request_dice_roll = MethodType(_request_dice_roll_with_replay_results, game)

    @staticmethod
    def _request_option_label_by_action_id(request_payload: dict[str, Any], chosen_action_id: str) -> tuple[str, int | None]:
        target_action_id = str(chosen_action_id or "")
        for idx, entry in enumerate(list(request_payload.get("options", []) or [])):
            option = dict(entry or {})
            payload = dict(option.get("payload", {}) or {})
            if str(payload.get("action_id", "") or "") == target_action_id:
                return str(option.get("label", "") or ""), idx
        return "", None

    @staticmethod
    def _pending_request_match_identity_from_payload(payload: dict[str, Any]) -> dict[str, tuple[str, ...]]:
        context = dict(dict(payload or {}).get("context", {}) or {})
        options = list(dict(payload or {}).get("options", []) or [])
        option_payloads = [
            dict(dict(option or {}).get("payload", {}) or {})
            for option in options
        ]
        return ReplayStoreReader._pending_request_match_identity(context, option_payloads)

    @staticmethod
    def _pending_request_match_identity_from_request(request: DecisionRequest) -> dict[str, tuple[str, ...]]:
        context = dict(getattr(request, "context", {}) or {})
        option_payloads = [
            dict(getattr(option, "payload", {}) or {})
            for option in list(getattr(request, "options", []) or [])
        ]
        return ReplayStoreReader._pending_request_match_identity(context, option_payloads)

    @staticmethod
    def _pending_request_match_identity(
        context: dict[str, Any],
        option_payloads: list[dict[str, Any]],
    ) -> dict[str, tuple[str, ...]]:
        context_keys = (
            "unit_id",
            "transport_id",
            "target_unit_id",
            "enemy_unit_id",
            "phase_name",
            "phase_step",
            "selection_purpose",
            "ability",
            "movement_type",
            "placement_kind",
            "roll_id",
            "roll_type",
        )
        identity: dict[str, tuple[str, ...]] = {}
        for key in context_keys:
            value = str(dict(context or {}).get(key, "") or "")
            if value:
                identity[f"context:{key}"] = (value,)

        option_keys = (
            "unit_id",
            "target_unit_id",
            "enemy_unit_id",
            "transport_id",
            "roll_id",
        )
        for key in option_keys:
            values = tuple(
                str(payload.get(key, "") or "")
                for payload in option_payloads
                if str(payload.get(key, "") or "")
            )
            if values:
                identity[f"option:{key}"] = values
        return identity

    @staticmethod
    def _pending_request_match_identity_matches(
        expected: dict[str, tuple[str, ...]],
        actual: dict[str, tuple[str, ...]],
    ) -> bool:
        for key, expected_value in expected.items():
            if not expected_value:
                continue
            if actual.get(key, ()) != expected_value:
                return False
        return True

    @staticmethod
    def _find_matching_pending_request(game: Game, request_payload: dict[str, Any]) -> DecisionRequest | None:
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        decision_type = str(request_payload.get("decision_type", "") or "")
        prompt = str(request_payload.get("prompt", "") or "")
        player_id = request_payload.get("player_id", None)
        expected_labels = tuple(
            str(dict(option or {}).get("label", "") or "")
            for option in list(request_payload.get("options", []) or [])
        )
        expected_identity = ReplayStoreReader._pending_request_match_identity_from_payload(request_payload)
        for request in list(queue.list() or []):
            if decision_type and str(getattr(request, "decision_type", "") or "") != decision_type:
                continue
            if prompt and str(getattr(request, "prompt", "") or "") != prompt:
                continue
            request_player_id = getattr(request, "player_id", None)
            if player_id is not None and str(request_player_id or "") != str(player_id or ""):
                continue
            request_labels = tuple(
                str(getattr(option, "label", "") or "")
                for option in list(getattr(request, "options", []) or [])
            )
            if expected_labels and request_labels != expected_labels:
                continue
            request_identity = ReplayStoreReader._pending_request_match_identity_from_request(request)
            if not ReplayStoreReader._pending_request_match_identity_matches(expected_identity, request_identity):
                continue
            return request
        return None

    @staticmethod
    def _skip_payload_for_option(option: object | None) -> dict[str, Any]:
        payload = dict(getattr(option, "payload", {}) or {}) if option is not None else {}
        result_payload: dict[str, Any] = {}
        if bool(payload.get("skip", False)):
            result_payload["skipped"] = True
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            result_payload["skipped"] = True
        return result_payload

    @staticmethod
    def _recorded_result_payload(record: dict[str, Any], chosen_action_id: str) -> dict[str, Any]:
        for candidate in list(record.get("candidates", []) or []):
            payload = dict(candidate or {})
            if str(payload.get("action_id", "") or "") != str(chosen_action_id or ""):
                continue
            metadata = dict(payload.get("metadata", {}) or {})
            resolved = metadata.get("resolved_result_payload")
            if isinstance(resolved, dict):
                return dict(resolved)
            return {}
        return {}

    @staticmethod
    def _result_payload_for_option_replay(
        request: DecisionRequest,
        record: dict[str, Any],
        chosen_action_id: str,
        option: object | None,
        *,
        request_payload: dict[str, Any] | None = None,
        game: Game | None = None,
    ) -> dict[str, Any]:
        payload = ReplayStoreReader._skip_payload_for_option(option)
        if str(getattr(request, "decision_type", "") or "") == "REQUEST_DICE_ROLL":
            roll_results = ReplayStoreReader._recorded_roll_results(record)
            if roll_results:
                payload["roll_results"] = roll_results
        recorded_payload = ReplayStoreReader._recorded_result_payload(record, chosen_action_id)
        if recorded_payload:
            if game is not None:
                recorded_payload = ReplayStoreReader._action_params_for_runtime(
                    game,
                    recorded_payload,
                    request_payload,
                    record,
                )
            payload.update(recorded_payload)
        return ReplayStoreReader._ensure_replay_result_payload(
            game,
            request,
            payload,
            option_payload=dict(getattr(option, "payload", {}) or {}) if option is not None else {},
        )

    @staticmethod
    def _ensure_replay_result_payload(
        game: Game | None,
        request: DecisionRequest,
        payload: dict[str, Any],
        *,
        option_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision_type = str(getattr(request, "decision_type", "") or "")
        if decision_type != "DECLARE_SHOTS":
            return payload
        action = str(payload.get("action", "") or dict(option_payload or {}).get("action", "") or "").strip().lower()
        if action in {"skip", "pass"} or bool(payload.get("skipped", False)) or bool(payload.get("skip", False)):
            return payload
        declarations = payload.get("declarations")
        if isinstance(declarations, list) and declarations:
            return payload
        from .headless_policy_controller import HeadlessPolicyDecisionController

        seed_payload = dict(option_payload or {})
        seed_payload.update(payload)
        declarations = HeadlessPolicyDecisionController._default_shooting_declarations(game, request, seed_payload)
        if declarations:
            seed_payload["declarations"] = declarations
            return seed_payload
        return payload

    @staticmethod
    def _result_for_record(
        request: DecisionRequest,
        record: dict[str, Any],
        *,
        request_payload: dict[str, Any] | None = None,
        game: Game | None = None,
    ) -> DecisionResult:
        chosen_action_id = str(record.get("chosen_action_id", "") or "")
        if not chosen_action_id:
            raise ValueError("Replay record is missing chosen_action_id.")
        for option in list(getattr(request, "options", []) or []):
            option_id = getattr(option, "option_id", None)
            action_id = request.action_id_for_option_id(option_id)
            if str(action_id) == chosen_action_id:
                return DecisionResult(
                    decision_id=str(getattr(request, "decision_id", "") or ""),
                    player_id=getattr(request, "player_id", None),
                    option_id=option_id,
                    payload=ReplayStoreReader._result_payload_for_option_replay(
                        request,
                        record,
                        chosen_action_id,
                        option,
                        request_payload=request_payload,
                        game=game,
                    ),
                )
        if request_payload:
            chosen_label, chosen_index = ReplayStoreReader._request_option_label_by_action_id(
                request_payload,
                chosen_action_id,
            )
            if chosen_label:
                for option in list(getattr(request, "options", []) or []):
                    if str(getattr(option, "label", "") or "") != chosen_label:
                        continue
                    return DecisionResult(
                        decision_id=str(getattr(request, "decision_id", "") or ""),
                        player_id=getattr(request, "player_id", None),
                        option_id=getattr(option, "option_id", None),
                        payload=ReplayStoreReader._result_payload_for_option_replay(
                            request,
                            record,
                            chosen_action_id,
                            option,
                            request_payload=request_payload,
                            game=game,
                        ),
                    )
            if chosen_index is not None:
                options = list(getattr(request, "options", []) or [])
                if 0 <= int(chosen_index) < len(options):
                    option = options[int(chosen_index)]
                    return DecisionResult(
                        decision_id=str(getattr(request, "decision_id", "") or ""),
                        player_id=getattr(request, "player_id", None),
                        option_id=getattr(option, "option_id", None),
                        payload=ReplayStoreReader._result_payload_for_option_replay(
                            request,
                            record,
                            chosen_action_id,
                            option,
                            request_payload=request_payload,
                            game=game,
                        ),
                    )
        if not bool(record.get("human_action_injected", False)):
            raise ValueError("Replay chosen_action_id does not map to an option_id.")
        chosen_candidate = None
        for candidate in list(record.get("candidates", []) or []):
            payload = dict(candidate or {})
            if str(payload.get("action_id", "") or "") == chosen_action_id:
                chosen_candidate = payload
                break
        if chosen_candidate is None:
            raise ValueError("Replay chosen_action_id is missing from candidates.")
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
            raise ValueError("Replay request has no selectable option for injected action replay.")
        params = dict(chosen_candidate.get("params", {}) or {})
        if game is not None:
            params = ReplayStoreReader._action_params_for_runtime(game, params, request_payload, record)
        result_payload = dict(params)
        result_payload["human_action_params"] = dict(params)
        return DecisionResult(
            decision_id=str(getattr(request, "decision_id", "") or ""),
            player_id=getattr(request, "player_id", None),
            option_id=fallback_option_id,
            payload=result_payload,
        )

    @staticmethod
    def _selected_option_payload(request: DecisionRequest, result: DecisionResult) -> dict[str, Any]:
        for option in list(getattr(request, "options", []) or []):
            if getattr(option, "option_id", None) == getattr(result, "option_id", None):
                return dict(getattr(option, "payload", {}) or {})
        return {}

    @classmethod
    def _apply_reconstructed_setup_side_effects(
        cls,
        game: Game,
        request: DecisionRequest,
        result: DecisionResult,
    ) -> None:
        if request is None or result is None:
            return
        if str(getattr(request, "decision_type", "") or "") != "CHOOSE_DEPLOYMENT_ZONE":
            return
        chooser_player_id = str(getattr(request, "player_id", None) or getattr(result, "player_id", None) or "")
        players = list(getattr(game, "players", []) or [])
        if len(players) != 2 or not chooser_player_id:
            return
        chooser_idx = next(
            (idx for idx, player in enumerate(players) if str(getattr(player, "id", "") or "") == chooser_player_id),
            None,
        )
        if chooser_idx is None:
            return
        chosen_payload = cls._selected_option_payload(request, result)
        chosen_zone_choice_id = str(chosen_payload.get("zone_choice_id", "") or "")
        chosen_zone_key = str(chosen_payload.get("zone_key", "") or "")
        if not chosen_zone_choice_id and not chosen_zone_key:
            return
        available_zone_choices = list(dict(getattr(request, "context", {}) or {}).get("available_zone_choices", []) or [])
        chosen_zone: dict[str, Any] | None = None
        other_zone: dict[str, Any] | None = None
        for entry in available_zone_choices:
            data = dict(entry or {})
            choice_id = str(data.get("zone_choice_id", "") or "")
            zone_key = str(data.get("zone_key", "") or "")
            if (
                (chosen_zone_choice_id and choice_id == chosen_zone_choice_id)
                or (chosen_zone_key and zone_key == chosen_zone_key)
            ):
                chosen_zone = data
            elif other_zone is None:
                other_zone = data
        if chosen_zone is None or other_zone is None:
            return
        existing_by_type: dict[str, dict[str, Any]] = {}
        for zone in list(getattr(game, "deployment_zones", {}).values() or []):
            if not isinstance(zone, dict):
                continue
            zone_type = str(zone.get("zone_type", "") or "")
            if zone_type and zone_type not in existing_by_type:
                existing_by_type[zone_type] = dict(zone)

        def _zone_for_choice(choice: dict[str, Any]) -> dict[str, Any]:
            zone_type = str(choice.get("zone_type", "") or "")
            zone_payload = dict(existing_by_type.get(zone_type, {}) or {})
            if not zone_payload:
                return {}
            zone_payload["name"] = str(choice.get("zone_name", "") or zone_payload.get("name", "") or "")
            zone_payload["zone_type"] = zone_type or str(zone_payload.get("zone_type", "") or "")
            return zone_payload

        chooser = players[int(chooser_idx)]
        other = players[1 - int(chooser_idx)]
        chooser_zone = _zone_for_choice(chosen_zone)
        other_zone_payload = _zone_for_choice(other_zone)
        if not chooser_zone or not other_zone_payload:
            return
        # Deployment-zone ownership is applied by the surrounding setup flow, not by
        # the CHOOSE_DEPLOYMENT_ZONE decision handler itself. Replay reconstruction
        # needs to restore that player->zone mapping explicitly so later deployment
        # legality checks use the recorded zone ownership.
        game.deployment_zones = {
            str(getattr(chooser, "id", "") or ""): chooser_zone,
            str(getattr(other, "id", "") or ""): other_zone_payload,
        }
        game.defender_index = int(chooser_idx)
        game.attacker_index = int(1 - chooser_idx)
        game.deployment_turn_index = int(chooser_idx)
        game.current_player_index = int(chooser_idx)

    @staticmethod
    def _prime_request_state(game: Game, request: DecisionRequest) -> None:
        if request is None:
            return
        from .decision_kinds import DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL

        if request.decision_type not in (DECISION_REQUEST_DICE_ROLL, DECISION_SELECT_DICE_REROLL):
            return
        ctx = dict(getattr(request, "context", {}) or {})
        roll_id = ctx.get("roll_id")
        if roll_id is None:
            return
        roll_manager = getattr(game, "roll_manager", None)
        if roll_manager is None:
            raise RuntimeError("Replay game missing roll manager for dice decision replay.")
        normalized_roll_id = int(roll_id)
        state = roll_manager.get_roll(normalized_roll_id)
        if state is not None:
            if request.decision_type != DECISION_SELECT_DICE_REROLL:
                return
            if str(getattr(state, "status", "") or "") == "rolled":
                return
        else:
            from .dice_rolls import DiceRollState

            spec = dict(ctx.get("roll_spec", {}) or {})
            state = DiceRollState(
                roll_id=normalized_roll_id,
                player_id=getattr(request, "player_id", None),
                spec=spec,
                status="pending",
            )
            roll_manager.rolls[normalized_roll_id] = state
        if request.decision_type != DECISION_SELECT_DICE_REROLL:
            return
        proxy_game = SimpleNamespace(
            is_authoritative=bool(getattr(game, "is_authoritative", True)),
            event_system=None,
            request_decision=lambda _request: None,
            roll_manager=roll_manager,
            entity_registry=getattr(game, "entity_registry", None),
            players=getattr(game, "players", None),
            map=getattr(game, "map", None),
        )
        try:
            roll_manager.resolve_roll(
                proxy_game,
                normalized_roll_id,
                result_payload={},
                actor_player_id=getattr(request, "player_id", None),
            )
        except RuntimeError:
            return

    @staticmethod
    def _dice_request_already_resolved(game: Game, payload: dict[str, Any] | None) -> bool:
        if not payload:
            return False
        from .decision_kinds import DECISION_REQUEST_DICE_ROLL

        if str(dict(payload or {}).get("decision_type", "") or "") != DECISION_REQUEST_DICE_ROLL:
            return False
        ctx = dict(dict(payload or {}).get("context", {}) or {})
        roll_id = ctx.get("roll_id")
        if roll_id is None:
            return False
        roll_manager = getattr(game, "roll_manager", None)
        if roll_manager is None:
            return False
        try:
            state = roll_manager.get_roll(int(roll_id))
        except (TypeError, ValueError):
            return False
        if state is None:
            return False
        return str(getattr(state, "status", "") or "") == "rolled"

    def _advance_until_request_pending(
        self,
        game: Game,
        replay_events: list[dict[str, Any]],
        replay_cursor: int,
        decision_id: str,
        request_payload: dict[str, Any] | None,
        *,
        stop_event_id: int | None = None,
    ) -> tuple[DecisionRequest | None, int]:
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            raise RuntimeError("Replay game missing decision queue.")
        request = queue.get(decision_id)
        target_request_payload = dict(request_payload or {}) if request_payload is not None else None
        while request is None:
            if target_request_payload:
                matched_request = self._find_matching_pending_request(game, target_request_payload)
                if matched_request is not None:
                    return matched_request, replay_cursor
            if replay_cursor >= len(replay_events):
                return None, replay_cursor
            event = dict(replay_events[replay_cursor] or {})
            if stop_event_id is not None:
                event_id = int(event.get("event_id", 0) or 0)
                if event_id > int(stop_event_id):
                    return None, replay_cursor
            replay_cursor += 1
            event_type = str(event.get("type", "") or "")
            payload = dict(event.get("payload", {}) or {})
            if event_type == "decision_requested":
                if str(payload.get("decision_id", "") or "") == decision_id:
                    target_request_payload = payload
                    matched_request = self._find_matching_pending_request(game, target_request_payload)
                    if matched_request is not None:
                        return matched_request, replay_cursor
                    continue
                pending = self._find_matching_pending_request(game, payload)
                if pending is None:
                    pending = self._decision_request_from_payload(game, payload)
                    if queue.get(str(getattr(pending, "decision_id", "") or "")) is None:
                        self._prime_request_state(game, pending)
                        queue.add(pending)
            elif event_type == "decision_resolved":
                if str(payload.get("decision_id", "") or "") == decision_id:
                    if target_request_payload is not None:
                        return None, replay_cursor
                    raise ValueError(
                        f"Replay reached decision_resolved before request {decision_id} became pending."
                    )
            elif event_type == "command_rejected":
                continue
            elif event_type == "command_applied":
                command = self._command_from_payload(game, payload)
                if command.kind in (CMD_REQUEST_DECISION, CMD_RESOLVE_DECISION):
                    continue
                try:
                    game.apply_command(command)
                except RuntimeError as exc:
                    if (
                        command.kind == CMD_EXECUTE_SETUP_PHASE
                        and "Deployment requires manual UI or explicit decision_makers." in str(exc)
                    ):
                        continue
                    raise
            elif event_type == "dice_roll":
                from ..utility.dice import get_dice_roll
                from ..utility.game_context import game_context

                with game_context(game):
                    get_dice_roll(int(payload.get("die_faces", 6) or 6))
            request = queue.get(decision_id)
        return request, replay_cursor

    def reconstruct_game_at_decision(self, decision_idx: int, *, strict: bool = True) -> Game:
        max_count = self.decision_count()
        idx = int(decision_idx)
        if idx < 0:
            raise ValueError("decision_idx must be >= 0.")
        if idx > max_count:
            raise IndexError(f"decision_idx {idx} exceeds replay decision count {max_count}.")
        keyframe = self._nearest_keyframe(idx)
        snapshot = dict(_unpack_json(bytes(keyframe["snapshot_blob"])))
        start_idx = int(keyframe["decision_idx"])
        if idx == start_idx:
            game = Game.load_snapshot(snapshot)
            if idx > 0:
                self._sync_reconstructed_game_to_step(game, self.get_step(idx))
            return game

        with self._connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT decision_id, request_blob, decision_record_blob, event_end_id
                    FROM decision_steps
                    WHERE decision_idx > ? AND decision_idx <= ?
                    ORDER BY decision_idx ASC
                    """,
                    (int(start_idx), int(idx)),
                )
            )
        end_event_id = int(keyframe["event_id"])
        for row in rows:
            if row["event_end_id"] is not None:
                end_event_id = max(end_event_id, int(row["event_end_id"]))
        event_tail = self._events_between(int(keyframe["event_id"]), int(end_event_id))
        game = self._prepare_reconstruction_game(snapshot)
        recorded_roll_queue: list[dict[str, Any]] = []
        for row in rows:
            if row["request_blob"] is None:
                continue
            row_payload = dict(_unpack_json(bytes(row["request_blob"])))
            row_record = dict(_unpack_json(bytes(row["decision_record_blob"])))
            queue_entry = self._roll_queue_entry_from_record(row_payload, row_record)
            if queue_entry is not None:
                recorded_roll_queue.append(queue_entry)
        setattr(game, "_replay_recorded_roll_results_queue", recorded_roll_queue)
        self._install_replay_dice_request_adapter(game)
        replay_cursor = 0

        for row in rows:
            decision_id = str(row["decision_id"] or "")
            record = dict(_unpack_json(bytes(row["decision_record_blob"])))
            payload = None
            if row["request_blob"] is not None:
                payload = dict(_unpack_json(bytes(row["request_blob"])))
            if self._dice_request_already_resolved(game, payload):
                continue
            request, replay_cursor = self._advance_until_request_pending(
                game,
                event_tail,
                replay_cursor,
                decision_id,
                payload,
                stop_event_id=int(row["event_end_id"]) if row["event_end_id"] is not None else None,
            )
            if request is None:
                if payload is None:
                    raise ValueError(f"Replay is missing decision request payload for {decision_id}.")
                runtime_payload = self._request_payload_for_runtime(game, payload, record)
                request = self._decision_request_from_payload(game, runtime_payload)
                self._prime_request_state(game, request)
                game.decision_queue.add(request)
            result = self._result_for_record(request, record, request_payload=payload, game=game)
            apply_result = game.resolve_decision(result)
            if bool(getattr(apply_result, "ok", False)):
                self._apply_reconstructed_setup_side_effects(game, request, result)
            if bool(strict) and not bool(getattr(apply_result, "ok", False)):
                errors = list(getattr(apply_result, "errors", ()) or ())
                raise ValueError(f"Replay failed at decision {decision_id}: {errors}")
        if idx > 0:
            self._sync_reconstructed_game_to_step(game, self.get_step(idx))
        return game


def enable_decision_replay_recording(
    game: Game,
    *,
    replay_path: str | Path,
    keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
    session_id: str | None = None,
    label: str | None = None,
) -> Path:
    if game is None:
        raise ValueError("Game is required.")
    path = Path(replay_path)
    recorder = ReplayStoreRecorder(path, keyframe_interval=keyframe_interval)
    recorder.initialize_for_game(game, session_id=session_id, label=label)
    event_system = getattr(game, "event_system", None)
    if event_system is None:
        raise RuntimeError("Game missing event_system.")
    event_system.unsubscribe_group(REPLAY_RECORDING_GROUP)

    def _on_decision_requested(
        *,
        request: DecisionRequest | None = None,
        game: Game | None = None,
        **_kwargs: Any,
    ) -> None:
        active_game = game if game is not None else getattr(request, "game", None)
        if active_game is None or request is None:
            return
        recorder.record_decision_request(active_game, request)

    def _on_decision_resolved(
        *,
        request: DecisionRequest | None = None,
        result: DecisionResult | None = None,
        game: Game | None = None,
        **_kwargs: Any,
    ) -> None:
        active_game = game if game is not None else getattr(request, "game", None)
        if active_game is None or request is None or result is None:
            return
        recorder.record_resolution(active_game, request, result, defer_keyframe=False)

    def _on_decision_settled(
        *,
        request: DecisionRequest | None = None,
        result: DecisionResult | None = None,
        game: Game | None = None,
        accepted: bool | None = None,
        **_kwargs: Any,
    ) -> None:
        if not bool(accepted):
            return
        active_game = game if game is not None else getattr(request, "game", None)
        if active_game is None or request is None:
            return
        decision_id = str(getattr(request, "decision_id", "") or "")
        if result is not None and decision_id and not recorder.has_decision_step(decision_id):
            recorder.record_resolution(active_game, request, result, defer_keyframe=True)
        recorder.finalize_resolution(active_game, request)

    def _place_replay_listener_after_event_log(event_name: str, callback: Any) -> None:
        try:
            subscribers = list(getattr(event_system, "subscribers", {}).get(event_name, []) or [])
            replay_entry = None
            remaining = []
            for entry in subscribers:
                entry_callback, group = entry
                if entry_callback is callback and group == REPLAY_RECORDING_GROUP:
                    replay_entry = entry
                    continue
                remaining.append(entry)
            if replay_entry is None:
                return
            insert_at = 0
            for index, (_callback, group) in enumerate(remaining):
                if str(group or "") == "deterministic_event_log":
                    insert_at = index + 1
            remaining.insert(insert_at, replay_entry)
            event_system.subscribers[event_name] = remaining
        except (AttributeError, TypeError, ValueError):
            pass

    event_system.subscribe_group(REPLAY_RECORDING_GROUP, "decision_requested", _on_decision_requested)
    _place_replay_listener_after_event_log("decision_requested", _on_decision_requested)
    event_system.subscribe_group(REPLAY_RECORDING_GROUP, "decision_resolved", _on_decision_resolved)
    _place_replay_listener_after_event_log("decision_resolved", _on_decision_resolved)
    event_system.subscribe_group(REPLAY_RECORDING_GROUP, "decision_settled", _on_decision_settled)
    setattr(game, "_decision_replay_recorder", recorder)
    setattr(game, "_decision_replay_path", str(path))
    return path


def disable_decision_replay_recording(game: Game) -> None:
    if game is None:
        return
    recorder = getattr(game, "_decision_replay_recorder", None)
    flush_runtime_tail = getattr(recorder, "flush_runtime_tail", None)
    if callable(flush_runtime_tail):
        flush_runtime_tail(game, write_keyframe=True)
    close_recorder = getattr(recorder, "close", None)
    if callable(close_recorder):
        close_recorder()
    event_system = getattr(game, "event_system", None)
    if event_system is not None:
        event_system.unsubscribe_group(REPLAY_RECORDING_GROUP)
    if hasattr(game, "_decision_replay_recorder"):
        delattr(game, "_decision_replay_recorder")
