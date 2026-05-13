from __future__ import annotations

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_REACTIVE_MOVE
from warhammer40k_ai.engine.reactive_movement import (
    DESTINATION_ANY_LEGAL_NORMAL_MOVE,
    END_STATE_NORMAL_MOVE_END,
    MOVE_KIND_NORMAL,
    ReactiveMoveSpec,
    build_reactive_move_request,
)


pytestmark = pytest.mark.preview


SPACE_MARINES_SOURCE = "wc_2026_05_05_space_marines_faction_focus"


def test_reactive_movement_fixture_is_preview_gated_and_sourced() -> None:
    spec = ReactiveMoveSpec(
        spec_id="reactive_evasion_preview",
        trigger_window="opponent_movement_phase:after_enemy_unit_ends_normal_move",
        source_unit_id="unit:speeder",
        target_reference={"enemy_unit_id": "unit:raiders"},
        move_kind=MOVE_KIND_NORMAL,
        max_distance_expr="D3+3",
        destination_policy=DESTINATION_ANY_LEGAL_NORMAL_MOVE,
        end_state_policy=END_STATE_NORMAL_MOVE_END,
        source_provenance=(SPACE_MARINES_SOURCE,),
    )

    request = build_reactive_move_request(
        player_id="player:space_marines",
        active_player_id="player:opponent",
        spec=spec,
    )

    assert request.decision_type == DECISION_REACTIVE_MOVE
    assert request.context["preview_gated"] is True
    assert request.context["reactive_move_spec"]["source_provenance"] == [SPACE_MARINES_SOURCE]
    assert request.context["opponent_turn"] is True
    assert {candidate.params["action"] for candidate in request.candidates} == {"move", "skip"}
