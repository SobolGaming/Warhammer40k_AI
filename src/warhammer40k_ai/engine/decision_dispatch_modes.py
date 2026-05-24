from __future__ import annotations

from typing import Any, Mapping

from .decisions import DecisionRequest


DISPATCH_MODE_TOP_LEVEL = "top_level"
DISPATCH_MODE_SYNC_CHILD = "sync_child"
DISPATCH_MODE_INTERRUPT = "interrupt"
STACK_DISPATCH_MODES = frozenset({DISPATCH_MODE_SYNC_CHILD, DISPATCH_MODE_INTERRUPT})

DISPATCH_CONTEXT_KEYS = frozenset(
    {
        "dispatch_mode",
        "interrupt_window",
        "interrupt_source",
        "interrupts_decision_id",
        "parent_decision_id",
        "parent_decision_type",
        "parent_player_id",
        "parent_phase_name",
        "blocking_parent",
        "resume_parent_after_resolution",
        "out_of_phase",
        "synchronous",
    }
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def dispatch_mode_from_context(context: Mapping[str, Any] | None) -> str:
    ctx = dict(context or {})
    mode = _clean_text(ctx.get("dispatch_mode", "")).lower()
    if mode:
        return mode
    if bool(ctx.get("interrupt_window", False)):
        return DISPATCH_MODE_INTERRUPT
    if bool(ctx.get("synchronous", False)):
        return DISPATCH_MODE_SYNC_CHILD
    return ""


def is_stack_dispatch_mode(mode: str) -> bool:
    return _clean_text(mode).lower() in STACK_DISPATCH_MODES


def dispatch_context_from_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    ctx = dict(context or {})
    return {key: ctx[key] for key in DISPATCH_CONTEXT_KEYS if key in ctx}


def apply_interrupt_context(
    context: Mapping[str, Any] | None,
    *,
    interrupt_window: str,
    out_of_phase: bool = True,
    blocking_parent: bool = True,
    resume_parent_after_resolution: bool = True,
    source: str = "",
    parent_decision_id: str = "",
    interrupts_decision_id: str = "",
) -> dict[str, Any]:
    window = _clean_text(interrupt_window)
    if not window:
        raise ValueError("Interrupt dispatch context requires interrupt_window.")
    decorated = dict(context or {})
    decorated["dispatch_mode"] = DISPATCH_MODE_INTERRUPT
    decorated["interrupt_window"] = window
    decorated["out_of_phase"] = bool(out_of_phase)
    decorated["blocking_parent"] = bool(blocking_parent)
    decorated["resume_parent_after_resolution"] = bool(resume_parent_after_resolution)
    source_key = _clean_text(source)
    if source_key:
        decorated["interrupt_source"] = source_key
    parent_id = _clean_text(parent_decision_id)
    if parent_id:
        decorated["parent_decision_id"] = parent_id
    interrupted_id = _clean_text(interrupts_decision_id)
    if interrupted_id:
        decorated["interrupts_decision_id"] = interrupted_id
    return decorated


def mark_interrupt_request(
    request: DecisionRequest,
    *,
    interrupt_window: str,
    out_of_phase: bool = True,
    blocking_parent: bool = True,
    resume_parent_after_resolution: bool = True,
    source: str = "",
    parent_decision_id: str = "",
    interrupts_decision_id: str = "",
) -> DecisionRequest:
    request.context = apply_interrupt_context(
        dict(getattr(request, "context", {}) or {}),
        interrupt_window=interrupt_window,
        out_of_phase=out_of_phase,
        blocking_parent=blocking_parent,
        resume_parent_after_resolution=resume_parent_after_resolution,
        source=source,
        parent_decision_id=parent_decision_id,
        interrupts_decision_id=interrupts_decision_id,
    )
    return request


def apply_sync_child_context(
    context: Mapping[str, Any] | None,
    *,
    parent_decision_id: str = "",
    out_of_phase: bool = False,
    blocking_parent: bool = True,
    resume_parent_after_resolution: bool = True,
    source: str = "",
) -> dict[str, Any]:
    decorated = dict(context or {})
    decorated["dispatch_mode"] = DISPATCH_MODE_SYNC_CHILD
    decorated["out_of_phase"] = bool(out_of_phase)
    decorated["blocking_parent"] = bool(blocking_parent)
    decorated["resume_parent_after_resolution"] = bool(resume_parent_after_resolution)
    parent_id = _clean_text(parent_decision_id)
    if parent_id:
        decorated["parent_decision_id"] = parent_id
    source_key = _clean_text(source)
    if source_key:
        decorated["interrupt_source"] = source_key
    return decorated


def mark_sync_child_request(
    request: DecisionRequest,
    *,
    parent_decision_id: str = "",
    out_of_phase: bool = False,
    blocking_parent: bool = True,
    resume_parent_after_resolution: bool = True,
    source: str = "",
) -> DecisionRequest:
    request.context = apply_sync_child_context(
        dict(getattr(request, "context", {}) or {}),
        parent_decision_id=parent_decision_id,
        out_of_phase=out_of_phase,
        blocking_parent=blocking_parent,
        resume_parent_after_resolution=resume_parent_after_resolution,
        source=source,
    )
    return request
