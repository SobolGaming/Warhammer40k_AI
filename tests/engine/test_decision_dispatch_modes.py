from __future__ import annotations

import pytest

from warhammer40k_ai.engine.decision_dispatch_modes import (
    DISPATCH_MODE_INTERRUPT,
    DISPATCH_MODE_SYNC_CHILD,
    apply_interrupt_context,
    apply_sync_child_context,
    dispatch_context_from_context,
    dispatch_mode_from_context,
    is_stack_dispatch_mode,
)


def test_interrupt_context_helper_marks_blocking_interrupt() -> None:
    context = apply_interrupt_context(
        {"ability": "heroic_intervention"},
        interrupt_window="after_enemy_charge_move",
        source="heroic_intervention",
    )

    assert context["ability"] == "heroic_intervention"
    assert context["dispatch_mode"] == DISPATCH_MODE_INTERRUPT
    assert context["interrupt_window"] == "after_enemy_charge_move"
    assert context["interrupt_source"] == "heroic_intervention"
    assert context["out_of_phase"] is True
    assert context["blocking_parent"] is True
    assert context["resume_parent_after_resolution"] is True


def test_interrupt_context_helper_requires_window() -> None:
    with pytest.raises(ValueError, match="interrupt_window"):
        apply_interrupt_context({}, interrupt_window="")


def test_sync_child_context_helper_marks_parent_child_request() -> None:
    context = apply_sync_child_context(
        {"movement_type": "heroic_intervention"},
        parent_decision_id="decision:parent",
        out_of_phase=True,
        source="heroic_intervention",
    )

    assert context["movement_type"] == "heroic_intervention"
    assert context["dispatch_mode"] == DISPATCH_MODE_SYNC_CHILD
    assert context["parent_decision_id"] == "decision:parent"
    assert context["out_of_phase"] is True
    assert context["interrupt_source"] == "heroic_intervention"


def test_dispatch_mode_infers_legacy_contexts_and_extracts_only_dispatch_fields() -> None:
    assert dispatch_mode_from_context({"interrupt_window": "start_move"}) == DISPATCH_MODE_INTERRUPT
    assert dispatch_mode_from_context({"synchronous": True}) == DISPATCH_MODE_SYNC_CHILD
    assert is_stack_dispatch_mode("interrupt")

    dispatch_context = dispatch_context_from_context(
        {
            "dispatch_mode": "interrupt",
            "interrupt_window": "start_move",
            "unit_id": "unit:1",
            "movement_type": "normal",
        }
    )

    assert dispatch_context == {
        "dispatch_mode": "interrupt",
        "interrupt_window": "start_move",
    }
