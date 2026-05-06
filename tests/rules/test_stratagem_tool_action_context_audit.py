from __future__ import annotations

from scripts.audit_stratagem_tool_action_context import build_audit


def test_stratagem_tool_action_context_audit_has_no_unknown_unsafe_descriptors() -> None:
    audit = build_audit(implemented_only=True)

    assert audit["descriptor_count"] > 900
    assert audit["unsafe_count"] == 0
    assert audit["category_counts"].get("broad_phase_blocked_until_bound_context", 0) == 0
    assert audit["category_counts"]["trigger_window"] > 0
    assert audit["category_counts"]["generic_broad_phase"] > 0
    assert audit["category_counts"]["generic_phase_context_provider"] > 0


def test_all_descriptors_have_no_blocked_bound_context_cases() -> None:
    audit = build_audit(implemented_only=False)

    assert audit["unsafe_count"] == 0
    assert audit["category_counts"].get("broad_phase_blocked_until_bound_context", 0) == 0
