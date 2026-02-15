from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..engine.decisions import DecisionRequest


def option_entries(request: Optional[DecisionRequest]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if request is None:
        return entries
    for opt in list(getattr(request, "options", []) or []):
        entries.append(
            {
                "option_id": opt.option_id,
                "label": str(getattr(opt, "label", "") or ""),
                "payload": dict(getattr(opt, "payload", {}) or {}),
            }
        )
    return entries


def option_id_for_action(request: Optional[DecisionRequest], action: str) -> str:
    if request is None:
        return ""
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("action", "") or "") == action:
            return opt.option_id
    return first_option_id(request)


def option_id_for_payload(request: Optional[DecisionRequest], key: str, value: object) -> str:
    if request is None:
        return ""
    wanted = str(value or "")
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get(key, "") or "") == wanted:
            return opt.option_id
    return ""


def option_id_for_hue_degrees(request: Optional[DecisionRequest], hue_degrees: int) -> str:
    if request is None:
        return ""
    hue = int(hue_degrees) % 360
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        raw = payload.get("hue_degrees", None)
        if raw is None:
            continue
        if int(raw) % 360 == hue:
            return opt.option_id
    return ""


def first_option_id(request: Optional[DecisionRequest]) -> str:
    options = list(getattr(request, "options", []) or [])
    if options:
        return options[0].option_id
    return ""
