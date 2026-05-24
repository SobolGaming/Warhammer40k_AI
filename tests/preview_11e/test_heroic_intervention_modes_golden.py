from __future__ import annotations

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_HEROIC_INTERVENTION_MODE
from warhammer40k_ai.engine.reactive_movement import StratagemMode, build_heroic_intervention_mode_request


pytestmark = pytest.mark.preview


SPACE_MARINES_SOURCE = "wc_2026_05_05_space_marines_faction_focus"


def test_heroic_intervention_modes_fixture_is_preview_gated_and_sourced() -> None:
    request = build_heroic_intervention_mode_request(
        player_id="player:defender",
        stratagem_name="Heroic Intervention",
        source_unit_id="unit:champion",
        target_unit_id="unit:raiders",
        modes=(
            StratagemMode(
                mode_id="into_the_fray",
                cp_delta=0,
                charge_target_policy="enemy_unit_that_ended_normal_move",
                max_roll_cap=12,
                source_provenance=(SPACE_MARINES_SOURCE,),
            ),
            StratagemMode(
                mode_id="leap_to_defend",
                cp_delta=-1,
                charge_target_policy="closest_visible_enemy",
                max_roll_cap=6,
                source_provenance=(SPACE_MARINES_SOURCE,),
            ),
        ),
    )

    assert request.decision_type == DECISION_SELECT_HEROIC_INTERVENTION_MODE
    assert request.context["preview_gated"] is True
    assert request.context["dispatch_mode"] == "interrupt"
    assert request.context["interrupt_window"] == "after_enemy_charge_move"
    assert request.context["out_of_phase"] is True
    assert {
        tuple(mode["source_provenance"])
        for mode in request.context["stratagem_modes"]
    } == {(SPACE_MARINES_SOURCE,)}
    assert {candidate.params["mode_id"] for candidate in request.candidates} == {
        "into_the_fray",
        "leap_to_defend",
    }
