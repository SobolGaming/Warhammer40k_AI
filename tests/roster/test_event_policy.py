from __future__ import annotations

from warhammer40k_ai.roster.event_policy import (
    EVENT_POLICY_SCHEMA_ID,
    EventPolicyDescriptor,
    chapter_approved_10e_event_policy,
    preview_new40k_event_policy,
)


def test_10th_style_and_preview_event_policies_coexist_as_data() -> None:
    current = chapter_approved_10e_event_policy()
    preview = preview_new40k_event_policy()

    assert current.event_policy_schema_id == EVENT_POLICY_SCHEMA_ID
    assert preview.event_policy_schema_id == EVENT_POLICY_SCHEMA_ID
    assert current.event_policy_id == "event_policy:chapter_approved_10e_singles_v1"
    assert preview.event_policy_id == "event_policy:preview_new40k_locked_force_disposition_v1"
    assert current.event_policy_id != preview.event_policy_id
    assert current.force_disposition_lock_mode == "flexible"
    assert preview.force_disposition_lock_mode == "event_locked"
    assert current.mission_policy is not None
    assert preview.mission_policy is not None
    assert current.mission_policy.challenge_mode == "not_used"
    assert preview.mission_policy.terrain_layout_count_per_pairing == 3
    assert current.max_rounds == 5
    assert preview.max_rounds == 5

    current_roundtrip = EventPolicyDescriptor.from_dict(current.to_dict())
    preview_roundtrip = EventPolicyDescriptor.from_dict(preview.to_dict())

    assert current_roundtrip.to_dict() == current.to_dict()
    assert preview_roundtrip.to_dict() == preview.to_dict()

