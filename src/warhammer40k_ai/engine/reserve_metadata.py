from __future__ import annotations

from typing import Any


def _special_rules(unit: Any) -> dict:
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    return special_rules


def _set_reserve_status(unit: Any, status: str) -> None:
    setter = getattr(unit, "set_reserve_status", None)
    if callable(setter):
        setter(status)
    else:
        setattr(unit, "reserve_status", status)


def _unit_must_start_in_reserves(unit: Any) -> bool:
    checker = getattr(unit, "must_start_in_reserves", None)
    return bool(checker()) if callable(checker) else False


def _int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def set_reserve_start_metadata(
    unit: Any,
    *,
    started: bool,
    reserve_status: str | None = None,
    source: str = "",
    mandatory_start: bool = False,
    latest_arrival_round: int = 3,
) -> None:
    if reserve_status is not None:
        _set_reserve_status(unit, str(reserve_status or "deployed"))
    setattr(unit, "_started_in_reserves", bool(started))
    special_rules = _special_rules(unit)
    if started:
        resolved_source = str(source or ("must_start_in_reserves" if mandatory_start else "deployment_choice"))
        resolved_latest = _int_or(latest_arrival_round or 3, 3)
        special_rules["reserve_source"] = resolved_source
        special_rules["reserve_mandatory_start"] = bool(mandatory_start)
        special_rules["reserve_latest_arrival_round"] = resolved_latest
        setattr(unit, "reserve_source", resolved_source)
        setattr(unit, "reserve_mandatory_start", bool(mandatory_start))
        setattr(unit, "reserve_latest_arrival_round", resolved_latest)
    else:
        for key in (
            "reserve_source",
            "reserve_mandatory_start",
            "reserve_latest_arrival_round",
            "reserve_last_arrival_failure",
        ):
            special_rules.pop(key, None)
        for attr in (
            "reserve_source",
            "reserve_mandatory_start",
            "reserve_latest_arrival_round",
            "reserve_last_arrival_failure",
        ):
            if hasattr(unit, attr):
                delattr(unit, attr)
    unit.special_rules = special_rules


def ensure_reserve_start_metadata(unit: Any) -> dict:
    special_rules = _special_rules(unit)
    started = bool(getattr(unit, "_started_in_reserves", False))
    reserve_status = str(getattr(unit, "reserve_status", "") or "").strip().lower()
    in_reserves = reserve_status in {"reserves", "strategic_reserves"}
    if not started and in_reserves:
        started = True
        setattr(unit, "_started_in_reserves", True)

    mandatory_start = bool(
        getattr(unit, "reserve_mandatory_start", False)
        or special_rules.get("reserve_mandatory_start", False)
        or _unit_must_start_in_reserves(unit)
    )
    source = str(getattr(unit, "reserve_source", "") or special_rules.get("reserve_source", "") or "").strip()
    latest_round = _int_or(
        getattr(unit, "reserve_latest_arrival_round", 0)
        or special_rules.get("reserve_latest_arrival_round", 0)
        or 0,
        0,
    )
    metadata_incomplete = bool(started and (not source or latest_round <= 0))
    if started:
        if not source:
            source = "must_start_in_reserves" if mandatory_start else "deployment_choice"
        if latest_round <= 0:
            latest_round = 3
        special_rules["reserve_source"] = source
        special_rules["reserve_mandatory_start"] = bool(mandatory_start)
        special_rules["reserve_latest_arrival_round"] = latest_round
        setattr(unit, "reserve_source", source)
        setattr(unit, "reserve_mandatory_start", bool(mandatory_start))
        setattr(unit, "reserve_latest_arrival_round", latest_round)
        unit.special_rules = special_rules
    return {
        "reserve_source": source,
        "reserve_mandatory_start": bool(mandatory_start),
        "reserve_latest_arrival_round": latest_round,
        "reserve_status": reserve_status,
        "started_in_reserves": bool(started),
        "metadata_incomplete": metadata_incomplete,
    }
