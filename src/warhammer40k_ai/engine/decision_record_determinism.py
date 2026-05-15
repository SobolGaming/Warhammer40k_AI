from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


VOLATILE_DECISION_RECORD_KEYS = frozenset(
    {
        "created_at",
        "elapsed_ms",
        "requested_at",
        "resolved_at",
        "solver_ms",
        "started_at",
        "completed_at",
        "timestamp",
        "wall_clock_ms",
    }
)


def strip_volatile_decision_record_fields(value: Any) -> Any:
    """Return a JSON-like value with wall-clock-derived telemetry removed."""

    if isinstance(value, Mapping):
        return {
            str(key): strip_volatile_decision_record_fields(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) not in VOLATILE_DECISION_RECORD_KEYS
        }
    if isinstance(value, list):
        return [strip_volatile_decision_record_fields(inner) for inner in value]
    if isinstance(value, tuple):
        return [strip_volatile_decision_record_fields(inner) for inner in value]
    return value


def decision_record_determinism_signature(record: Mapping[str, Any]) -> dict[str, Any]:
    """Lightweight policy/replay signature for profiled-vs-unprofiled equality checks."""

    candidates = [
        {
            "action_id": str(dict(candidate or {}).get("action_id", "") or ""),
            "params": strip_volatile_decision_record_fields(dict(candidate or {}).get("params", {}) or {}),
            "metadata": strip_volatile_decision_record_fields(dict(candidate or {}).get("metadata", {}) or {}),
        }
        for candidate in list(dict(record or {}).get("candidates", []) or [])
        if isinstance(candidate, Mapping)
    ]
    projected = {
        "turn_id": dict(record or {}).get("turn_id"),
        "phase": dict(record or {}).get("phase"),
        "decision_id": str(dict(record or {}).get("decision_id", "") or ""),
        "decision_type": str(dict(record or {}).get("decision_type", "") or ""),
        "global_seed": dict(record or {}).get("global_seed"),
        "decision_seed": dict(record or {}).get("decision_seed"),
        "chosen_action_id": str(dict(record or {}).get("chosen_action_id", "") or ""),
        "valid": dict(record or {}).get("valid"),
        "human_action_injected": bool(dict(record or {}).get("human_action_injected", False)),
        "request_context": strip_volatile_decision_record_fields(
            dict(record or {}).get("request_context", {}) or {}
        ),
        "candidates": candidates,
        "mask": list(dict(record or {}).get("mask", []) or []),
        "invalid_attempt": strip_volatile_decision_record_fields(
            dict(record or {}).get("invalid_attempt", {}) or {}
        ),
        "rejection_reason": str(dict(record or {}).get("rejection_reason", "") or ""),
        "outcome": strip_volatile_decision_record_fields(dict(record or {}).get("outcome", {}) or {}),
    }
    return strip_volatile_decision_record_fields(projected)


def decision_record_determinism_digest(records: Iterable[Mapping[str, Any]]) -> str:
    signatures = [decision_record_determinism_signature(record) for record in list(records or [])]
    payload = json.dumps(signatures, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
