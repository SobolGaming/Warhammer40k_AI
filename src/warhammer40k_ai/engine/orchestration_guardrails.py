from __future__ import annotations

import json
from typing import Any


GENERAL_PLAN_BUILD_BUDGET_MS = 150
DEPLOYMENT_PLAN_BUILD_BUDGET_MS = 250
DEPLOYMENT_REPAIR_BUDGET_MS = 100
COMMANDER_PLAN_BUILD_BUDGET_MS = 600
COMMANDER_REPAIR_BUDGET_MS = 150

ORCHESTRATION_CONTEXT_PAYLOAD_WARNING_BYTES = 8192
ORCHESTRATION_CONTEXT_PAYLOAD_HARD_LIMIT_BYTES = 65536


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


def canonical_payload_size_bytes(payload: object) -> int:
    encoded = json.dumps(
        _json_safe(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return int(len(encoded))


def context_payload_guardrail_report(
    context: dict[str, Any],
    *,
    warning_bytes: int = ORCHESTRATION_CONTEXT_PAYLOAD_WARNING_BYTES,
    hard_limit_bytes: int = ORCHESTRATION_CONTEXT_PAYLOAD_HARD_LIMIT_BYTES,
) -> dict[str, Any]:
    full_plan_keys = sorted(
        key
        for key in (
            "general_plan",
            "deployment_plan",
            "battle_round_plan",
            "deployment_order_bundle",
            "prebattle_order_bundle",
            "commander_order_bundle",
        )
        if key in dict(context or {})
    )
    payload_bytes = canonical_payload_size_bytes(dict(context or {}))
    return {
        "context_payload_bytes": int(payload_bytes),
        "context_payload_warning_bytes": int(warning_bytes),
        "context_payload_hard_limit_bytes": int(hard_limit_bytes),
        "context_payload_over_warning": bool(payload_bytes > int(warning_bytes)),
        "context_payload_within_hard_limit": bool(payload_bytes <= int(hard_limit_bytes)),
        "context_full_plan_keys": full_plan_keys,
        "context_cache_key_safe": bool(not full_plan_keys and payload_bytes <= int(warning_bytes)),
    }
