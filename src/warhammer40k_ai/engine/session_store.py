from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .game import Game
from .replay_store import (
    DEFAULT_KEYFRAME_INTERVAL,
    REPLAY_DB_FILENAME,
    REPLAY_FORMAT_ID,
    ReplayStoreReader,
    enable_decision_replay_recording,
)

DEFAULT_BASE_DIR = Path("games") / "data"
MANIFEST_FILENAME = "manifest.json"
SNAPSHOT_FILENAME = "snapshot.json"
REPLAY_FILENAME = REPLAY_DB_FILENAME
AUTOSAVE_GROUP = "session_autosave"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_base_dir(base_dir: str | Path | None) -> Path:
    return Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR


def _session_dir(session_id: str, base_dir: Path) -> Path:
    return base_dir / str(session_id)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _phase_name(phase: object) -> str | None:
    if phase is None:
        return None
    name = getattr(phase, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(phase)


def _infer_agent_type(player: object) -> str:
    agent_type = getattr(player, "agent_type", None)
    if isinstance(agent_type, str) and agent_type:
        return agent_type
    if bool(getattr(player, "is_ai", False)):
        return "ai"
    return "human"


def _player_stub(player: object) -> dict:
    control = getattr(player, "control", None)
    control_name = control.name if hasattr(control, "name") else (str(control) if control is not None else None)
    score_fn = getattr(player, "get_vp_breakdown", None)
    score = score_fn() if callable(score_fn) else {}
    army = getattr(player, "army", None)
    get_detachment_types = getattr(army, "get_detachment_types", None) if army is not None else None
    get_primary_detachment_type = (
        getattr(army, "get_primary_detachment_type", None) if army is not None else None
    )
    detachment_types = list(get_detachment_types() or []) if callable(get_detachment_types) else []
    return {
        "player_id": getattr(player, "id", None),
        "name": getattr(player, "name", None),
        "control": control_name,
        "agent_type": _infer_agent_type(player),
        "score": score,
        "faction": getattr(army, "faction", None) if army is not None else None,
        "primary_detachment_type": (
            get_primary_detachment_type() if callable(get_primary_detachment_type) else None
        ),
        "detachment_types": detachment_types,
    }


def _build_manifest(game: Game, session_id: str, *, label: str | None = None) -> dict:
    players = list(getattr(game, "players", []) or [])
    current_player = None
    get_current_player = getattr(game, "get_current_player", None)
    if callable(get_current_player):
        current_player = get_current_player()
    ruleset_bundle = getattr(game, "ruleset_bundle", None)
    ruleset_payload = ruleset_bundle.to_dict() if ruleset_bundle is not None else {}
    replay_path = str(getattr(game, "_decision_replay_path", "") or "")
    replay_file = Path(replay_path).name if replay_path else None
    return {
        "session_id": str(session_id),
        "label": str(label) if label is not None else None,
        "created_at": None,
        "updated_at": None,
        "battle_round": int(getattr(game, "get_battle_round", lambda: 0)() or 0),
        "phase": _phase_name(getattr(game, "phase", None)),
        "current_player_id": getattr(current_player, "id", None),
        "ruleset": ruleset_payload,
        "replay_file": replay_file,
        "replay_format": REPLAY_FORMAT_ID if replay_file else None,
        "players": [_player_stub(p) for p in players],
    }


def create_session(
    game: Game,
    *,
    base_dir: str | Path | None = None,
    session_id: str | None = None,
    label: str | None = None,
) -> str:
    if game is None:
        raise ValueError("Game is required.")
    if session_id is None:
        session_id = str(uuid.uuid4())
    base_path = _resolve_base_dir(base_dir)
    session_path = _session_dir(session_id, base_path)
    if session_path.exists():
        raise FileExistsError(f"Session already exists: {session_id}")
    manifest = _build_manifest(game, session_id, label=label)
    now = _utc_now()
    manifest["created_at"] = now
    manifest["updated_at"] = now
    _write_json(session_path / MANIFEST_FILENAME, manifest)
    setattr(game, "session_id", str(session_id))
    return str(session_id)


def save_session_snapshot(
    game: Game,
    *,
    base_dir: str | Path | None = None,
    session_id: str | None = None,
    label: str | None = None,
) -> Path:
    if game is None:
        raise ValueError("Game is required.")
    session_id = session_id or getattr(game, "session_id", None)
    if not session_id:
        raise ValueError("Session id is required.")
    base_path = _resolve_base_dir(base_dir)
    session_path = _session_dir(session_id, base_path)
    session_path.mkdir(parents=True, exist_ok=True)

    snapshot = game.save_snapshot()
    snapshot_path = session_path / SNAPSHOT_FILENAME
    _write_json(snapshot_path, snapshot)

    event_log = getattr(game, "event_log", None)
    if event_log is not None:
        event_log.trim_through()

    manifest_path = session_path / MANIFEST_FILENAME
    manifest = _build_manifest(game, session_id, label=label)
    if manifest_path.exists():
        existing = _read_json(manifest_path)
        manifest["created_at"] = existing.get("created_at")
        if label is None:
            manifest["label"] = existing.get("label")
    now = _utc_now()
    if not manifest.get("created_at"):
        manifest["created_at"] = now
    manifest["updated_at"] = now
    _write_json(manifest_path, manifest)
    setattr(game, "session_id", str(session_id))
    return snapshot_path


def load_session_snapshot(
    session_id: str,
    *,
    base_dir: str | Path | None = None,
) -> Game:
    base_path = _resolve_base_dir(base_dir)
    session_path = _session_dir(session_id, base_path)
    snapshot_path = session_path / SNAPSHOT_FILENAME
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found for session {session_id}.")
    snapshot = _read_json(snapshot_path)
    game = Game.load_snapshot(snapshot)
    setattr(game, "session_id", str(session_id))
    return game


def _session_replay_path(session_id: str, base_dir: Path) -> Path:
    return _session_dir(session_id, base_dir) / REPLAY_FILENAME


def enable_session_replay_recording(
    game: Game,
    *,
    base_dir: str | Path | None = None,
    session_id: str | None = None,
    label: str | None = None,
    keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
) -> Path:
    if game is None:
        raise ValueError("Game is required.")
    session_id = session_id or getattr(game, "session_id", None)
    if not session_id:
        session_id = create_session(game, base_dir=base_dir, label=label)
    base_path = _resolve_base_dir(base_dir)
    replay_path = _session_replay_path(str(session_id), base_path)
    recorded_path = enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=keyframe_interval,
        session_id=str(session_id),
        label=label,
    )
    manifest_path = _session_dir(str(session_id), base_path) / MANIFEST_FILENAME
    manifest = _build_manifest(game, str(session_id), label=label)
    if manifest_path.exists():
        existing = _read_json(manifest_path)
        manifest["created_at"] = existing.get("created_at")
        if label is None:
            manifest["label"] = existing.get("label")
    now = _utc_now()
    if not manifest.get("created_at"):
        manifest["created_at"] = now
    manifest["updated_at"] = now
    _write_json(manifest_path, manifest)
    return recorded_path


def load_session_replay_reader(
    session_id: str,
    *,
    base_dir: str | Path | None = None,
) -> ReplayStoreReader:
    base_path = _resolve_base_dir(base_dir)
    replay_path = _session_replay_path(str(session_id), base_path)
    if not replay_path.exists():
        raise FileNotFoundError(f"Replay store not found for session {session_id}.")
    return ReplayStoreReader(replay_path)


def list_sessions(base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    base_path = _resolve_base_dir(base_dir)
    if not base_path.exists():
        return []
    sessions: list[dict[str, Any]] = []
    for entry in sorted(base_path.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        manifest_path = entry / MANIFEST_FILENAME
        if not manifest_path.exists():
            continue
        data = _read_json(manifest_path)
        if "session_id" not in data:
            data["session_id"] = entry.name
        sessions.append(data)
    return sessions


def delete_session(session_id: str, *, base_dir: str | Path | None = None) -> None:
    base_path = _resolve_base_dir(base_dir)
    session_path = _session_dir(session_id, base_path)
    if not session_path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    for path in sorted(session_path.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    session_path.rmdir()


def enable_phase_end_autosave(
    game: Game,
    *,
    base_dir: str | Path | None = None,
    session_id: str | None = None,
    label: str | None = None,
    enable_replay: bool = True,
    replay_keyframe_interval: int = DEFAULT_KEYFRAME_INTERVAL,
) -> str:
    if game is None:
        raise ValueError("Game is required.")
    session_id = session_id or getattr(game, "session_id", None)
    if not session_id:
        session_id = create_session(game, base_dir=base_dir, label=label)
    if bool(enable_replay):
        enable_session_replay_recording(
            game,
            base_dir=base_dir,
            session_id=session_id,
            label=label,
            keyframe_interval=replay_keyframe_interval,
        )

    event_system = getattr(game, "event_system", None)
    if event_system is None:
        raise RuntimeError("Game missing event_system.")

    def _on_phase_end(**_kwargs: Any) -> None:
        if int(getattr(game, "get_battle_round", lambda: 0)() or 0) < 1:
            return
        save_session_snapshot(game, base_dir=base_dir, session_id=session_id, label=label)

    event_system.subscribe_group(AUTOSAVE_GROUP, "phase_end", _on_phase_end)
    return str(session_id)
