from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class DecisionOption:
    option_id: str
    label: str
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, label: str, payload: Optional[Dict[str, Any]] = None) -> "DecisionOption":
        return cls(
            option_id=str(uuid.uuid4()),
            label=str(label),
            payload=dict(payload or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "label": self.label,
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionOption":
        return cls(
            option_id=str(data.get("option_id", "") or ""),
            label=str(data.get("label", "") or ""),
            payload=dict(data.get("payload", {}) or {}),
        )


@dataclass
class DecisionRequest:
    decision_id: str
    player_id: Optional[str]
    prompt: str
    options: List[DecisionOption] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    timeout_seconds: Optional[float] = None

    @classmethod
    def create(
        cls,
        prompt: str,
        *,
        player_id: Optional[str] = None,
        options: Optional[Iterable[DecisionOption]] = None,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> "DecisionRequest":
        return cls(
            decision_id=str(uuid.uuid4()),
            player_id=player_id,
            prompt=str(prompt),
            options=list(options or []),
            context=dict(context or {}),
            timeout_seconds=timeout_seconds,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "player_id": self.player_id,
            "prompt": self.prompt,
            "options": [opt.to_dict() for opt in self.options],
            "context": dict(self.context or {}),
            "created_at": float(self.created_at or 0.0),
            "timeout_seconds": self.timeout_seconds,
        }

    @property
    def id(self) -> str:
        return self.decision_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRequest":
        return cls(
            decision_id=str(data.get("decision_id", "") or ""),
            player_id=data.get("player_id", None),
            prompt=str(data.get("prompt", "") or ""),
            options=[DecisionOption.from_dict(d) for d in list(data.get("options", []) or [])],
            context=dict(data.get("context", {}) or {}),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            timeout_seconds=data.get("timeout_seconds", None),
        )


@dataclass
class DecisionResult:
    decision_id: str
    player_id: Optional[str]
    option_id: Optional[str]
    payload: Dict[str, Any] = field(default_factory=dict)
    resolved_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "player_id": self.player_id,
            "option_id": self.option_id,
            "payload": dict(self.payload or {}),
            "resolved_at": float(self.resolved_at or 0.0),
        }

    @property
    def id(self) -> str:
        return self.decision_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionResult":
        return cls(
            decision_id=str(data.get("decision_id", "") or ""),
            player_id=data.get("player_id", None),
            option_id=data.get("option_id", None),
            payload=dict(data.get("payload", {}) or {}),
            resolved_at=float(data.get("resolved_at", 0.0) or 0.0),
        )


class DecisionQueue:
    def __init__(self):
        self._pending: List[DecisionRequest] = []

    def add(self, request: DecisionRequest) -> None:
        self._pending.append(request)

    def peek(self) -> Optional[DecisionRequest]:
        if not self._pending:
            return None
        return self._pending[0]

    def pop(self, decision_id: Optional[str] = None) -> Optional[DecisionRequest]:
        if not self._pending:
            return None
        if decision_id is None:
            return self._pending.pop(0)
        for idx, req in enumerate(self._pending):
            if req.decision_id == decision_id:
                return self._pending.pop(idx)
        return None

    def list(self) -> List[DecisionRequest]:
        return list(self._pending)
