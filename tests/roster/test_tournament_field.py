from __future__ import annotations

import pytest

from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.tournament_field import (
    OpponentSlice,
    TournamentFieldDistribution,
    WeightedChoice,
)


def _field_distribution(*, event_policy_id: str) -> TournamentFieldDistribution:
    return TournamentFieldDistribution(
        rules_bundle_id="rules_bundle:2026-04-14",
        event_policy_id=event_policy_id,
        terrain_layout_pack_id="terrain_pack:chapter_approved_2025_26",
        opponent_slices=(
            OpponentSlice(
                slice_id="slice:pressure_marines",
                weight=2,
                label="Pressure Marines",
                faction="Space Marines",
                detachment_type="Gladius Task Force",
                archetype_tags=("mid_board", "combined_arms"),
            ),
            OpponentSlice(
                slice_id="slice:indirect_guard",
                weight=1,
                label="Indirect Guard",
                faction="Astra Militarum",
                archetype_tags=("indirect", "castle"),
                army_blueprint=ArmyBlueprint(
                    faction="Astra Militarum",
                    detachments=[
                        DetachmentSelection(
                            selection_id="det_guard",
                            detachment_type="Combined Regiment",
                        )
                    ],
                    unit_entries=[
                        RosterEntry(
                            entry_id="entry_basilisk",
                            name="Basilisk",
                            detachment_selection_id="det_guard",
                        )
                    ],
                ),
            ),
        ),
        mission_distribution=(
            WeightedChoice(choice_id="mission:take_and_hold", weight=3),
            WeightedChoice(choice_id="mission:purge_the_foe", weight=1),
        ),
        deployment_distribution=(
            WeightedChoice(choice_id="deployment:dawn_of_war", weight=1),
            WeightedChoice(choice_id="deployment:hammer_and_anvil", weight=2),
        ),
        terrain_distribution=(
            WeightedChoice(choice_id="terrain:layout_1", weight=1),
            WeightedChoice(choice_id="terrain:layout_7", weight=2),
        ),
        round_count=5,
        event_format_name="Singles GT",
    )


def test_field_distribution_hashes_deterministically_for_reordered_scaled_weights() -> None:
    first = _field_distribution(event_policy_id="event_policy:chapter_approved_10e_singles_v1")
    second = TournamentFieldDistribution(
        rules_bundle_id="rules_bundle:2026-04-14",
        event_policy_id="event_policy:chapter_approved_10e_singles_v1",
        terrain_layout_pack_id="terrain_pack:chapter_approved_2025_26",
        opponent_slices=(
            {
                "slice_id": "slice:indirect_guard",
                "weight": 2,
                "label": "Indirect Guard",
                "faction": "Astra Militarum",
                "archetype_tags": ["castle", "indirect"],
                "army_blueprint": {
                    "faction": "Astra Militarum",
                    "detachments": [
                        {
                            "selection_id": "det_guard",
                            "detachment_type": "Combined Regiment",
                        }
                    ],
                    "unit_entries": [
                        {
                            "entry_id": "entry_basilisk",
                            "name": "Basilisk",
                            "detachment_selection_id": "det_guard",
                        }
                    ],
                },
            },
            {
                "slice_id": "slice:pressure_marines",
                "weight": 4,
                "label": "Pressure Marines",
                "faction": "Space Marines",
                "detachment_type": "Gladius Task Force",
                "archetype_tags": ["combined_arms", "mid_board"],
            },
        ),
        mission_distribution=(
            {"choice_id": "mission:purge_the_foe", "weight": 2},
            {"choice_id": "mission:take_and_hold", "weight": 6},
        ),
        deployment_distribution=(
            {"choice_id": "deployment:hammer_and_anvil", "weight": 4},
            {"choice_id": "deployment:dawn_of_war", "weight": 2},
        ),
        terrain_distribution=(
            {"choice_id": "terrain:layout_7", "weight": 4},
            {"choice_id": "terrain:layout_1", "weight": 2},
        ),
        round_count=5,
        event_format_name="Singles GT",
    )

    assert first.field_distribution_id == second.field_distribution_id
    assert first.normalized_opponent_slices == second.normalized_opponent_slices
    assert first.normalized_mission_distribution == second.normalized_mission_distribution
    assert first.normalized_deployment_distribution == second.normalized_deployment_distribution
    assert first.normalized_terrain_distribution == second.normalized_terrain_distribution


def test_field_distribution_rejects_empty_distributions() -> None:
    with pytest.raises(ValueError, match="opponent_slices"):
        TournamentFieldDistribution(
            rules_bundle_id="rules_bundle:2026-04-14",
            event_policy_id="event_policy:test",
            terrain_layout_pack_id="terrain_pack:test",
            opponent_slices=(),
            mission_distribution=(WeightedChoice(choice_id="mission:test", weight=1),),
            deployment_distribution=(WeightedChoice(choice_id="deployment:test", weight=1),),
            terrain_distribution=(WeightedChoice(choice_id="terrain:test", weight=1),),
        )

