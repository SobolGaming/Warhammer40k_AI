from __future__ import annotations

import pytest

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_REACTIVE_MOVE,
    DECISION_SELECT_HEROIC_INTERVENTION_MODE,
    DECISION_SELECT_REACTIVE_RESERVE_EXIT,
    DECISION_SURGE_MOVE,
)
from warhammer40k_ai.engine.reactive_movement import (
    DESTINATION_STRATEGIC_RESERVES,
    DESTINATION_TOWARD_CLOSEST_ENEMY,
    END_STATE_ATTEMPT_ENGAGED_WITH_CLOSEST_ENEMY,
    END_STATE_STRATEGIC_RESERVES,
    MOVE_KIND_NORMAL,
    MOVE_KIND_RESERVE_EXIT,
    MOVE_KIND_SURGE,
    ReactiveMoveSpec,
    StratagemMode,
    apply_reactive_reserve_exit_transition,
    build_heroic_intervention_mode_request,
    build_reactive_move_request,
)
from warhammer40k_ai.engine.stratagem_ledger import StratagemApplicationLedger, StratagemUseException


pytestmark = pytest.mark.preview


class _DummyUnit:
    def __init__(self, unit_id: str) -> None:
        self.id = unit_id
        self.reserve_status = "deployed"
        self.deployed = True
        self.arrived_from_reserves_this_turn = True
        self.position = (12.0, 18.0, 0.0)

    def set_reserve_status(self, status: str) -> None:
        self.reserve_status = status


class _DummyMap:
    def __init__(self, unit: _DummyUnit) -> None:
        self.units = [unit]


class _DummyManager:
    def __init__(self) -> None:
        self._current_phase_name = "Charge phase"
        self._used_stratagems_this_phase: set[str] = set()
        self._heroic_intervention_units_this_phase: set[str] = set()
        self._stratagem_use_exceptions_this_phase: list[dict] = []


def test_heroic_intervention_mode_fixture_records_mode_cp_and_charge_policy() -> None:
    modes = (
        StratagemMode(
            mode_id="into_the_fray",
            cp_delta=0,
            charge_target_policy="enemy_unit_that_ended_normal_move",
            max_roll_cap=12,
            source_provenance=("wc_2026_05_12_space_marines_faction_focus",),
        ),
        StratagemMode(
            mode_id="leap_to_defend",
            cp_delta=-1,
            charge_target_policy="closest_visible_enemy",
            max_roll_cap=6,
            source_provenance=("wc_2026_05_12_space_wolves_faction_focus",),
        ),
    )

    request = build_heroic_intervention_mode_request(
        player_id="player:defender",
        stratagem_name="Heroic Intervention",
        modes=modes,
        source_unit_id="unit:wolves",
        target_unit_id="unit:raiders",
    )

    assert request.decision_type == DECISION_SELECT_HEROIC_INTERVENTION_MODE
    assert request.context["selection_kind"] == "heroic_intervention_mode"
    by_mode = {candidate.params["mode_id"]: candidate for candidate in request.candidates}
    assert by_mode["leap_to_defend"].params["cp_delta"] == -1
    assert by_mode["leap_to_defend"].params["charge_target_policy"] == "closest_visible_enemy"
    assert by_mode["into_the_fray"].params["max_roll_cap"] == 12
    assert request.to_dict()["candidates"][0]["action_id"].startswith(DECISION_SELECT_HEROIC_INTERVENTION_MODE)


def test_reactive_normal_move_can_be_requested_during_opponent_movement_phase() -> None:
    spec = ReactiveMoveSpec(
        spec_id="reactive_evasion_preview",
        trigger_window="opponent_movement_phase:after_enemy_unit_ends_normal_move",
        source_unit_id="unit:intercessors",
        target_reference={"enemy_unit_id": "unit:ork_wagon"},
        move_kind=MOVE_KIND_NORMAL,
        max_distance_expr="D6",
        destination_policy="any_legal_normal_move",
        end_state_policy="normal_move_end",
        source_provenance=("wc_2026_05_12_space_marines_faction_focus",),
    )

    request = build_reactive_move_request(
        player_id="player:space_marines",
        active_player_id="player:orks",
        spec=spec,
    )

    assert request.decision_type == DECISION_REACTIVE_MOVE
    assert request.context["opponent_turn"] is True
    assert request.context["trigger_window"] == "opponent_movement_phase:after_enemy_unit_ends_normal_move"
    assert request.context["reactive_move_spec"]["spec_id"] == "reactive_evasion_preview"
    assert {candidate.params["action"] for candidate in request.candidates} == {"move", "skip"}


def test_surge_move_requires_toward_closest_enemy_end_state() -> None:
    spec = ReactiveMoveSpec(
        spec_id="rage_fuelled_response_preview",
        trigger_window="opponent_shooting_phase:after_enemy_unit_shot",
        source_unit_id="unit:berserkers",
        target_reference={"closest_enemy_policy": "exclude_aircraft"},
        move_kind=MOVE_KIND_SURGE,
        max_distance_expr="D3+3",
        destination_policy=DESTINATION_TOWARD_CLOSEST_ENEMY,
        end_state_policy=END_STATE_ATTEMPT_ENGAGED_WITH_CLOSEST_ENEMY,
        source_provenance=("wc_2026_05_12_world_eaters_faction_focus",),
    )

    request = build_reactive_move_request(
        player_id="player:world_eaters",
        active_player_id="player:astra_militarum",
        spec=spec,
    )

    assert request.decision_type == DECISION_SURGE_MOVE
    assert request.context["destination_policy"] == DESTINATION_TOWARD_CLOSEST_ENEMY
    assert request.context["end_state_policy"] == END_STATE_ATTEMPT_ENGAGED_WITH_CLOSEST_ENEMY
    assert request.candidates[0].metadata["candidate_kind"] == "reactive_move"


def test_reactive_reserve_exit_is_transition_not_teleport_payload() -> None:
    unit = _DummyUnit("unit:ravagers")
    game_map = _DummyMap(unit)
    spec = ReactiveMoveSpec(
        spec_id="reactive_reserve_exit_preview",
        trigger_window="opponent_movement_phase:end",
        source_unit_id=unit.id,
        move_kind=MOVE_KIND_RESERVE_EXIT,
        max_distance_expr="none",
        destination_policy=DESTINATION_STRATEGIC_RESERVES,
        end_state_policy=END_STATE_STRATEGIC_RESERVES,
        source_provenance=("wc_2026_05_12_chaos_daemons_faction_focus",),
    )

    request = build_reactive_move_request(
        player_id="player:daemons",
        active_player_id="player:adepta_sororitas",
        spec=spec,
    )
    transition = apply_reactive_reserve_exit_transition(unit, spec, game_map=game_map)

    assert request.decision_type == DECISION_SELECT_REACTIVE_RESERVE_EXIT
    assert transition.from_reserve_status == "deployed"
    assert transition.to_reserve_status == "strategic_reserves"
    assert transition.transition_kind == "reactive_reserve_exit"
    assert transition.to_dict().get("model_positions") is None
    assert unit.reserve_status == "strategic_reserves"
    assert unit.position == (12.0, 18.0, 0.0)
    assert unit not in game_map.units


def test_stratagem_ledger_repeat_exception_is_explicit_and_preserves_target_stacking() -> None:
    manager = _DummyManager()
    ledger = StratagemApplicationLedger(manager)
    ledger.mark_used_this_phase("Heroic Intervention")
    ledger.mark_target_used_this_phase("Heroic Intervention", "unit:already_used")
    exception = StratagemUseException(
        exception_id="preview_space_wolves_repeat_heroic_intervention",
        stratagem_name="Heroic Intervention",
        reason="Previewed exception: this use does not prevent other uses this phase.",
        allows_repeat_this_phase=True,
        still_enforce_target_stacking=True,
        source_id="wc_2026_05_12_space_wolves_faction_focus",
        source_provenance=("wc_2026_05_12_space_wolves_faction_focus",),
    )
    ledger.record_use_exception(exception)

    allowed = ledger.evaluate_use_request("Heroic Intervention", target_unit_id="unit:fresh")
    blocked = ledger.evaluate_use_request("Heroic Intervention", target_unit_id="unit:already_used")

    assert allowed.allowed is True
    assert allowed.allowed_by_exception is True
    assert allowed.exception_ids == ("preview_space_wolves_repeat_heroic_intervention",)
    assert allowed.reason_trace[0]["reason"] == "repeat_exception"
    assert blocked.allowed is False
    assert blocked.reason_trace[0]["invariant"] == "no_multiple_stratagem_applications_to_same_unit"
