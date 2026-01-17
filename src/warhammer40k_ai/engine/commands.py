from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid
from typing import Any, Dict, Optional


@dataclass
class GameCommand:
    command_id: str
    kind: str
    player_id: Optional[str]
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        kind: str,
        *,
        player_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "GameCommand":
        return cls(
            command_id=str(uuid.uuid4()),
            kind=str(kind),
            player_id=player_id,
            payload=dict(payload or {}),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "player_id": self.player_id,
            "payload": dict(self.payload or {}),
            "metadata": dict(self.metadata or {}),
            "created_at": float(self.created_at or 0.0),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameCommand":
        return cls(
            command_id=str(data.get("command_id", "") or ""),
            kind=str(data.get("kind", "") or ""),
            player_id=data.get("player_id", None),
            payload=dict(data.get("payload", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
            created_at=float(data.get("created_at", 0.0) or 0.0),
        )
