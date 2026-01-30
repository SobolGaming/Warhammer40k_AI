from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
import hashlib
import json
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

from ..utility.entity_ids import maybe_entity_id


def _canonicalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _canonicalize_value(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(v) for v in value]
    if isinstance(value, set):
        return sorted((_canonicalize_value(v) for v in value), key=lambda v: str(v))
    if is_dataclass(value):
        return _canonicalize_value(value.__dict__)
    entity_id = maybe_entity_id(value)
    if entity_id is not None:
        return entity_id
    type_name = f"{value.__class__.__module__}.{value.__class__.__name__}"
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return f"{type_name}:{name}"
    return type_name


def _derive_action_id(decision_type: str, label: str, payload: Dict[str, Any]) -> str:
    canonical = {
        "label": str(label or ""),
        "payload": _canonicalize_value(payload),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"{decision_type}:{digest}"


@dataclass(frozen=True)
class CandidateAction:
    action_id: str
    params: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": str(self.action_id or ""),
            "params": dict(self.params or {}),
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateAction":
        return cls(
            action_id=str(data.get("action_id", "") or ""),
            params=dict(data.get("params", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
        )


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
    decision_type: str
    prompt: str
    options: List[DecisionOption] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    candidates: List[CandidateAction] = field(default_factory=list)
    mask: List[bool] = field(default_factory=list)
    mask_reasons: List[Optional[str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    timeout_seconds: Optional[float] = None

    @classmethod
    def create(
        cls,
        decision_type: str,
        prompt: str,
        *,
        player_id: Optional[str] = None,
        options: Optional[Iterable[DecisionOption]] = None,
        context: Optional[Dict[str, Any]] = None,
        candidates: Optional[Iterable[CandidateAction]] = None,
        mask: Optional[Iterable[bool]] = None,
        mask_reasons: Optional[Iterable[Optional[str]]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> "DecisionRequest":
        dtype = str(decision_type or "").strip()
        if not dtype:
            raise ValueError("DecisionRequest requires decision_type.")
        req = cls(
            decision_id=str(uuid.uuid4()),
            player_id=player_id,
            decision_type=dtype,
            prompt=str(prompt),
            options=list(options or []),
            context=dict(context or {}),
            candidates=list(candidates or []),
            mask=list(mask or []),
            mask_reasons=list(mask_reasons or []),
            timeout_seconds=timeout_seconds,
        )
        req.finalize_candidates()
        return req

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "player_id": self.player_id,
            "decision_type": self.decision_type,
            "prompt": self.prompt,
            "options": [opt.to_dict() for opt in self.options],
            "context": dict(self.context or {}),
            "candidates": [c.to_dict() for c in list(self.candidates or [])],
            "mask": list(self.mask or []),
            "mask_reasons": list(self.mask_reasons or []),
            "created_at": float(self.created_at or 0.0),
            "timeout_seconds": self.timeout_seconds,
        }

    @property
    def id(self) -> str:
        return self.decision_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRequest":
        decision_type = str(data.get("decision_type", "") or "").strip()
        if not decision_type:
            raise ValueError("DecisionRequest missing decision_type.")
        req = cls(
            decision_id=str(data.get("decision_id", "") or ""),
            player_id=data.get("player_id", None),
            decision_type=decision_type,
            prompt=str(data.get("prompt", "") or ""),
            options=[DecisionOption.from_dict(d) for d in list(data.get("options", []) or [])],
            context=dict(data.get("context", {}) or {}),
            candidates=[CandidateAction.from_dict(d) for d in list(data.get("candidates", []) or [])],
            mask=list(data.get("mask", []) or []),
            mask_reasons=list(data.get("mask_reasons", []) or []),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            timeout_seconds=data.get("timeout_seconds", None),
        )
        req.finalize_candidates()
        return req

    def finalize_candidates(self) -> None:
        if not self.candidates:
            self.candidates = self._build_candidates_from_options()
        self._ensure_masks()

    def action_id_for_option_id(self, option_id: Optional[str]) -> str:
        if not option_id:
            return ""
        for opt in list(self.options or []):
            if opt.option_id == option_id:
                payload = dict(opt.payload or {})
                action_id = str(payload.get("action_id", "") or "").strip()
                if action_id:
                    return action_id
                action_id = _derive_action_id(self.decision_type, opt.label, payload)
                opt.payload["action_id"] = action_id
                return action_id
        return ""

    def candidate_mask_for_action_id(self, action_id: str) -> Optional[bool]:
        if not action_id:
            return None
        for idx, cand in enumerate(list(self.candidates or [])):
            if str(cand.action_id) == str(action_id):
                if idx < len(self.mask):
                    return bool(self.mask[idx])
        return None

    def _build_candidates_from_options(self) -> List[CandidateAction]:
        candidates: List[CandidateAction] = []
        seen: set[str] = set()
        for opt in list(self.options or []):
            payload = dict(opt.payload or {})
            action_id = str(payload.get("action_id", "") or "").strip()
            if not action_id:
                action_id = _derive_action_id(self.decision_type, opt.label, payload)
                opt.payload["action_id"] = action_id
            if action_id in seen:
                raise ValueError(f"Duplicate action_id in DecisionRequest: {action_id}")
            seen.add(action_id)
            params = dict(payload)
            params.pop("action_id", None)
            candidates.append(
                CandidateAction(
                    action_id=action_id,
                    params=params,
                    metadata={"label": str(opt.label or "")},
                )
            )
        candidates.sort(key=lambda cand: str(cand.action_id))
        return candidates

    def _ensure_masks(self) -> None:
        if not self.candidates:
            self.mask = []
            self.mask_reasons = []
            return
        if not self.mask:
            self.mask = [True] * len(self.candidates)
        if len(self.mask) != len(self.candidates):
            raise ValueError("DecisionRequest mask length must match candidates length.")
        self.mask = [bool(val) for val in self.mask]
        if self.mask_reasons and len(self.mask_reasons) != len(self.candidates):
            raise ValueError("DecisionRequest mask_reasons length must match candidates length.")


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

    def get(self, decision_id: str) -> Optional[DecisionRequest]:
        if not self._pending:
            return None
        for req in self._pending:
            if req.decision_id == decision_id:
                return req
        return None

    def list(self) -> List[DecisionRequest]:
        return list(self._pending)
