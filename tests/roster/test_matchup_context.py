from __future__ import annotations

import pytest

from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.event_policy import (
    chapter_approved_10e_event_policy,
    preview_new40k_event_policy,
)
from warhammer40k_ai.roster.matchup_context import compile_matchup_context
from warhammer40k_ai.roster.tournament_field import OpponentSlice, TournamentFieldDistribution, WeightedChoice


def _candidate_blueprint() -> ArmyBlueprint:
    return ArmyBlueprint(
        faction="Space Marines",
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="entry_captain",
                name="Captain",
                detachment_selection_id="det_gladius",
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="entry_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_gladius",
            ),
        ],
        force_disposition="Take and Hold",
        allowed_force_dispositions=["Take and Hold", "Purge the Foe"],
    )


def _field_for_policy(event_policy_id: str) -> TournamentFieldDistribution:
    return TournamentFieldDistribution(
        rules_bundle_id="rules_bundle:2026-04-14",
        event_policy_id=event_policy_id,
        terrain_layout_pack_id="terrain_pack:test",
        opponent_slices=(
            OpponentSlice(
                slice_id="slice:test",
                weight=1,
                label="Test Slice",
                faction="Necrons",
                archetype_tags=("durable",),
            ),
        ),
        mission_distribution=(WeightedChoice(choice_id="mission:test", weight=1),),
        deployment_distribution=(WeightedChoice(choice_id="deployment:test", weight=1),),
        terrain_distribution=(WeightedChoice(choice_id="terrain:test", weight=1),),
        round_count=5,
    )


def test_event_policy_differences_alter_matchup_context_deterministically() -> None:
    blueprint = _candidate_blueprint()
    current_policy = chapter_approved_10e_event_policy()
    preview_policy = preview_new40k_event_policy()

    current_context = compile_matchup_context(
        army_blueprint=blueprint,
        field_distribution=_field_for_policy(current_policy.event_policy_id),
        event_policy=current_policy,
    )
    current_repeat = compile_matchup_context(
        army_blueprint=blueprint.to_dict(),
        field_distribution=_field_for_policy(current_policy.event_policy_id).to_dict(),
        event_policy=current_policy.to_dict(),
    )
    preview_context = compile_matchup_context(
        army_blueprint=blueprint,
        field_distribution=_field_for_policy(preview_policy.event_policy_id),
        event_policy=preview_policy,
    )

    assert current_context.to_dict() == current_repeat.to_dict()
    assert current_context.matchup_context_id == current_repeat.matchup_context_id
    assert current_context.matchup_context_id != preview_context.matchup_context_id
    assert current_context.force_disposition_lock_mode == "flexible"
    assert preview_context.force_disposition_lock_mode == "event_locked"
    assert current_context.army_blueprint_hash == blueprint.army_blueprint_hash


def test_matchup_context_requires_matching_field_and_event_policy_ids() -> None:
    with pytest.raises(ValueError, match="field_distribution.event_policy_id"):
        compile_matchup_context(
            army_blueprint=_candidate_blueprint(),
            field_distribution=_field_for_policy("event_policy:chapter_approved_10e_singles_v1"),
            event_policy=preview_new40k_event_policy(),
        )
