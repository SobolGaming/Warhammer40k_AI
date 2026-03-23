from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import zlib

from .decisions import DecisionRequest, DecisionResult
from .game import Game
from .replay import prepare_replay

REPLAY_DB_FILENAME = "replay.sqlite3"
REPLAY_FORMAT_ID = "wh40k_replay_sqlite_v1"
REPLAY_FORMAT_VERSION = 1
REPLAY_RECORDING_GROUP = "decision_replay_recording"
DEFAULT_KEYFRAME_INTERVAL = 25


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
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _pack_json(value: Any) -> bytes:
    return zlib.compress(_canonical_json(value).encode("utf-8"), level=6)


def _unpack_json(blob: bytes) -> Any:
    return json.loads(zlib.decompress(blob).decode("utf-8"))


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
        self._ensure_schema()
        self._refresh_offsets()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

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
        snapshot_blob = _pack_json(snapshot)
        snapshot_hash = hashlib.sha256(_canonical_json(snapshot).encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO keyframes(decision_idx, event_id, snapshot_blob, snapshot_hash)
                VALUES(?, ?, ?, ?)
                """,
                (int(decision_idx), int(event_id), snapshot_blob, snapshot_hash),
            )
        return True

    def record_resolution(self, game: Game, request: DecisionRequest, result: DecisionResult) -> int:
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
        actor_player_id = str(
            getattr(result, "player_id", None)
            or getattr(request, "player_id", None)
            or str(record.get("player_id", "") or "")
        )
        controller_kind = _player_controller_kind(game, actor_player_id)
        with self._connect() as conn:
            cursor = conn.execute(
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
                    str(record.get("decision_id", "") or ""),
                    int(record.get("turn_id", 0) or 0),
                    str(record.get("phase", "") or ""),
                    actor_player_id,
                    controller_kind,
                    str(record.get("decision_type", "") or ""),
                    str(getattr(result, "option_id", "") or ""),
                    str(record.get("chosen_action_id", "") or ""),
                    1 if bool(record.get("valid", True)) else 0,
                    int(record.get("wall_clock_ms", 0) or 0),
                    (
                        int(record.get("time_budget_ms", 0) or 0)
                        if record.get("time_budget_ms", None) is not None
                        else None
                    ),
                    int(event_start_id) if event_start_id is not None else None,
                    int(event_end_id) if event_end_id is not None else None,
                    _pack_json(request_payload) if request_payload is not None else None,
                    _pack_json(record),
                ),
            )
            decision_idx = int(cursor.lastrowid or 0)
        if decision_idx <= 0:
            raise RuntimeError("Failed to persist replay decision step.")
        self.last_decision_idx = max(self.last_decision_idx, decision_idx)
        if (decision_idx % self.keyframe_interval) == 0:
            self._write_keyframe(game, decision_idx=decision_idx, event_id=int(self.last_event_id))
        self._set_meta(
            {
                "updated_at": _utc_now(),
                "last_decision_idx": int(self.last_decision_idx),
                "last_event_id": int(self.last_event_id),
            }
        )
        return decision_idx

    def decision_count(self) -> int:
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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

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
        steps = self.list_steps(offset=max(0, int(decision_idx) - 1), limit=1)
        if not steps or steps[0].decision_idx != int(decision_idx):
            raise IndexError(f"Decision step not found: {decision_idx}")
        return steps[0]

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

    def _nearest_keyframe(self, decision_idx: int) -> sqlite3.Row:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT keyframe_id, decision_idx, event_id, snapshot_blob
                FROM keyframes
                WHERE decision_idx <= ?
                ORDER BY decision_idx DESC
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
    def _decision_request_from_payload(payload: dict[str, Any]) -> DecisionRequest:
        request_data = {
            "decision_id": str(payload.get("decision_id", "") or ""),
            "player_id": payload.get("player_id", None),
            "decision_type": str(payload.get("decision_type", "") or ""),
            "prompt": str(payload.get("prompt", "") or ""),
            "options": list(payload.get("options", []) or []),
            "context": dict(payload.get("context", {}) or {}),
            "candidates": list(payload.get("candidates", []) or []),
            "mask": list(payload.get("mask", []) or []),
            "mask_reasons": list(payload.get("mask_reasons", []) or []),
            "timeout_seconds": payload.get("timeout_seconds", None),
        }
        return DecisionRequest.from_dict(request_data)

    @staticmethod
    def _result_for_record(request: DecisionRequest, record: dict[str, Any]) -> DecisionResult:
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
                    payload={},
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
        result_payload = dict(params)
        result_payload["human_action_params"] = dict(params)
        return DecisionResult(
            decision_id=str(getattr(request, "decision_id", "") or ""),
            player_id=getattr(request, "player_id", None),
            option_id=fallback_option_id,
            payload=result_payload,
        )

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
            return Game.load_snapshot(snapshot)

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
        game = prepare_replay(snapshot, event_tail)

        request_payloads: dict[str, dict[str, Any]] = {}
        for event in list(event_tail or []):
            if str(event.get("type", "") or "") != "decision_requested":
                continue
            payload = dict(event.get("payload", {}) or {})
            decision_id = str(payload.get("decision_id", "") or "")
            if decision_id and decision_id not in request_payloads:
                request_payloads[decision_id] = payload

        for row in rows:
            decision_id = str(row["decision_id"] or "")
            record = dict(_unpack_json(bytes(row["decision_record_blob"])))
            request = game.decision_queue.get(decision_id)
            if request is None:
                payload = None
                if row["request_blob"] is not None:
                    payload = dict(_unpack_json(bytes(row["request_blob"])))
                elif decision_id in request_payloads:
                    payload = dict(request_payloads[decision_id])
                if payload is None:
                    raise ValueError(f"Replay is missing decision request payload for {decision_id}.")
                request = self._decision_request_from_payload(payload)
                game.decision_queue.add(request)
                event_log = getattr(game, "event_log", None)
                if event_log is None:
                    raise RuntimeError("Replay game missing event log.")
                event_log.record(
                    "decision_requested",
                    actor_id=request.player_id,
                    payload=payload,
                    validate_payload=False,
                )
            result = self._result_for_record(request, record)
            apply_result = game.resolve_decision(result)
            if bool(strict) and not bool(getattr(apply_result, "ok", False)):
                errors = list(getattr(apply_result, "errors", ()) or ())
                raise ValueError(f"Replay failed at decision {decision_id}: {errors}")
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

    def _on_decision_settled(
        *,
        request: DecisionRequest | None = None,
        result: DecisionResult | None = None,
        game: Game | None = None,
        accepted: bool | None = None,
        **_kwargs: Any,
    ) -> None:
        active_game = game if game is not None else getattr(request, "game", None)
        if active_game is None or request is None or result is None:
            return
        if not bool(accepted):
            return
        recorder.record_resolution(active_game, request, result)

    event_system.subscribe_group(REPLAY_RECORDING_GROUP, "decision_settled", _on_decision_settled)
    setattr(game, "_decision_replay_recorder", recorder)
    setattr(game, "_decision_replay_path", str(path))
    return path


def disable_decision_replay_recording(game: Game) -> None:
    if game is None:
        return
    event_system = getattr(game, "event_system", None)
    if event_system is not None:
        event_system.unsubscribe_group(REPLAY_RECORDING_GROUP)
    if hasattr(game, "_decision_replay_recorder"):
        delattr(game, "_decision_replay_recorder")
