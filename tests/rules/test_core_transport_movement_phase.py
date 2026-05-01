from __future__ import annotations

from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_DISEMBARK,
    DECISION_EMBARK,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_MOVEMENT_ACTION,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.decision_requests import build_select_movement_action_request
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.movement_utils import compute_embark_candidates
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


pytestmark = pytest.mark.integration

WAHA = WahaHelper("wahapedia_data")


class _RecordingTransportRouter:
    def __init__(self, *, preferred_actions: tuple[str, ...]) -> None:
        self.preferred_actions = tuple(
            str(action or "").strip().lower() for action in preferred_actions
        )
        self.requests: list[DecisionRequest] = []

    def rank_legal_candidates(self, request: DecisionRequest, fallback_order):
        self.requests.append(request)
        remaining = list(fallback_order or [])
        ordered = []
        for preferred_action in self.preferred_actions:
            matches = [
                candidate
                for candidate in remaining
                if str(candidate.params.get("action", "") or "").strip().lower() == preferred_action
            ]
            ordered.extend(matches)
            match_ids = {id(candidate) for candidate in matches}
            remaining = [candidate for candidate in remaining if id(candidate) not in match_ids]
        return ordered + remaining

    def requests_of_type(self, decision_type: str) -> list[DecisionRequest]:
        return [
            request
            for request in self.requests
            if str(getattr(request, "decision_type", "") or "") == str(decision_type or "")
        ]


def _waha_unit(name: str, *, faction_id: str) -> Unit:
    datasheet = WAHA.get_datasheet(name, faction_id=faction_id)
    assert datasheet is not None, f"Missing Wahapedia datasheet: {name} ({faction_id})"
    return Unit(datasheet)


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    space_marines = Army("Space Marines")
    orks = Army("Orks")
    marine_player = Player("Adeptus Astartes", PlayerControl.LOCAL, space_marines)
    ork_player = Player("Orks", PlayerControl.REMOTE, orks)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[marine_player, ork_player])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1
    game.current_player_index = 0
    return game, marine_player, ork_player, space_marines, orks


def _place_single_model_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    assert game.map.place_unit(unit) is True


def _place_unit_grid(game: Game, unit: Unit, x: float, y: float, *, columns: int = 5) -> None:
    if unit in game.map.units:
        game.map.units.remove(unit)
    spacing = 1.8
    for idx, model in enumerate(unit.models):
        col = idx % columns
        row = idx // columns
        model.set_location(float(x) + col * spacing, float(y) + row * spacing, 0.0, 0.0)
    assert game.map.place_unit(unit) is True


def _position_payload(unit: Unit, positions: list[tuple[float, float, float, float]]) -> list[dict]:
    return [
        {
            "model_id": get_entity_id(model),
            "position": [float(x), float(y), float(z)],
            "facing": float(facing),
        }
        for model, (x, y, z, facing) in zip(unit.models, positions)
    ]


def _find_disembark_positions(
    game: Game,
    passenger: Unit,
    transport: Unit,
    *,
    max_distance: float = 3.0,
) -> list[tuple[float, float, float, float]]:
    positions = passenger._find_disembark_positions(
        transport.models[0].model_base,
        game.map,
        max_distance,
    )
    assert positions is not None
    assert len(positions) == len([model for model in passenger.models if model.is_alive])
    return positions


def _resolve_decision(
    game: Game,
    player: Player,
    request: DecisionRequest,
    option: DecisionOption,
    *,
    result_payload: dict | None = None,
) -> None:
    game.request_decision(request)
    result = resolve_decision_command(
        game,
        request,
        option.option_id,
        player_id=player.id,
        result_payload=dict(result_payload or {}),
    )
    assert result.ok, result.errors
    apply_result = result.value
    assert apply_result.ok, apply_result.errors


def _move_unit_by_decision(
    game: Game,
    player: Player,
    unit: Unit,
    positions: list[tuple[float, float, float, float]],
    *,
    movement_type: str = "move",
) -> None:
    option = DecisionOption.create(
        "Move",
        payload={"unit_id": get_entity_id(unit), "movement_type": movement_type},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        f"Move {unit.name}",
        player_id=player.id,
        options=[option],
        context={
            "unit_id": get_entity_id(unit),
            "movement_type": movement_type,
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
        },
    )
    _resolve_decision(
        game,
        player,
        request,
        option,
        result_payload={"model_positions": _position_payload(unit, positions)},
    )


def _embark_by_decision(game: Game, player: Player, passenger: Unit, transport: Unit) -> None:
    option = DecisionOption.create(
        "Embark",
        payload={"unit_id": get_entity_id(passenger), "transport_id": get_entity_id(transport)},
    )
    request = DecisionRequest.create(
        DECISION_EMBARK,
        f"Embark {passenger.name}",
        player_id=player.id,
        options=[option],
        context={"phase_name": "MOVEMENT_PHASE", "phase_step": "MOVE_UNITS"},
    )
    _resolve_decision(game, player, request, option)


def _disembark_by_decision(game: Game, player: Player, passenger: Unit, transport: Unit) -> None:
    positions = _find_disembark_positions(game, passenger, transport)
    option = DecisionOption.create(
        "Disembark",
        payload={"unit_id": get_entity_id(passenger), "transport_id": get_entity_id(transport)},
    )
    request = DecisionRequest.create(
        DECISION_DISEMBARK,
        f"Disembark {passenger.name}",
        player_id=player.id,
        options=[option],
        context={
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
            "disembark_max_distance": 3.0,
        },
    )
    _resolve_decision(
        game,
        player,
        request,
        option,
        result_payload={"model_positions": _position_payload(passenger, positions)},
    )


def _core_fixture() -> tuple[Game, Player, Unit, Unit, Unit]:
    game, marine_player, _ork_player, space_marines, orks = _build_game()
    rhino = _waha_unit("Rhino", faction_id="SM")
    tactical_squad = _waha_unit("Tactical Squad", faction_id="SM")
    boyz = _waha_unit("Boyz", faction_id="ORK")
    space_marines.add_unit(rhino)
    space_marines.add_unit(tactical_squad)
    orks.add_unit(boyz)
    game.rebuild_entity_registry()
    _place_single_model_unit(game, rhino, 20.0, 20.0)
    _place_unit_grid(game, boyz, 31.0, 20.0)
    return game, marine_player, rhino, tactical_squad, boyz


def _start_embarked(transport: Unit, passenger: Unit, game: Game) -> None:
    assert transport.add_passenger(passenger, game_map=game.map) is True
    passenger.round_state.embarked_this_round = False


def test_core_embark_after_qualifying_move_uses_real_wahapedia_transport_capacity() -> None:
    game, marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _place_unit_grid(game, tactical_squad, 5.0, 5.0)
    final_positions = _find_disembark_positions(game, tactical_squad, rhino)

    rhino.round_state.moved_this_round = True
    rhino.round_state.remained_stationary_this_round = False
    _move_unit_by_decision(game, marine_player, tactical_squad, final_positions)

    assert tactical_squad.round_state.moved_this_round is True
    assert tactical_squad in compute_embark_candidates(rhino, game.map)

    _embark_by_decision(game, marine_player, tactical_squad, rhino)

    assert tactical_squad.embarked_in is rhino
    assert tactical_squad not in game.map.units
    assert tactical_squad.round_state.embarked_this_round is True
    assert tactical_squad in rhino.transport_passengers


def test_reserve_arrival_that_only_counts_as_normal_move_cannot_embark() -> None:
    game, _marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    final_positions = _find_disembark_positions(game, tactical_squad, rhino)
    for model, position in zip(tactical_squad.models, final_positions):
        model.set_location(*position)
    assert game.map.place_unit(tactical_squad) is True

    tactical_squad.arrived_from_reserves_this_turn = True
    tactical_squad.round_state.reinforced_this_round = True
    tactical_squad.round_state.remained_stationary_this_round = False

    assert tactical_squad not in compute_embark_candidates(rhino, game.map)
    option = DecisionOption.create(
        "Embark",
        payload={"unit_id": get_entity_id(tactical_squad), "transport_id": get_entity_id(rhino)},
    )
    request = DecisionRequest.create(
        DECISION_EMBARK,
        f"Embark {tactical_squad.name}",
        player_id=game.get_current_player().id,
        options=[option],
        context={"phase_name": "MOVEMENT_PHASE", "phase_step": "MOVE_UNITS"},
    )
    game.request_decision(request)
    result = resolve_decision_command(game, request, option.option_id, player_id=game.get_current_player().id)
    assert result.ok is False
    assert "arrived from Reserves" in " ".join(result.errors)

    tactical_squad.embark(rhino, game_map=game.map)
    assert tactical_squad.embarked_in is None
    assert tactical_squad in game.map.units


def test_core_disembark_before_transport_moves_allows_later_move_or_advance_but_not_stationary() -> None:
    game, marine_player, rhino, tactical_squad, boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)

    _disembark_by_decision(game, marine_player, tactical_squad, rhino)

    assert tactical_squad.embarked_in is None
    assert tactical_squad in game.map.units
    assert tactical_squad.round_state.disembarked_this_round is True
    assert tactical_squad.round_state.moved_this_round is False
    assert tactical_squad.round_state.remained_stationary_this_round is False
    assert tactical_squad.round_state.cannot_remain_stationary_after_disembark is True
    assert tactical_squad.round_state.disembarked_cannot_charge is False
    assert tactical_squad.can_declare_charge_against(boyz, game) is True
    assert tactical_squad.remain_stationary() is False

    request = build_select_movement_action_request(
        tactical_squad,
        player_id=marine_player.id,
        phase_name="MOVEMENT_PHASE",
        phase_step="MOVE_UNITS",
        game_map=game.map,
    )
    assert request is not None
    actions = {str(option.payload.get("action_type")) for option in request.options}
    assert {"move", "advance"}.issubset(actions)
    assert "stationary" not in actions


def test_core_disembark_after_transport_normal_move_counts_as_moved_and_blocks_charge() -> None:
    game, marine_player, rhino, tactical_squad, boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)
    rhino.round_state.moved_this_round = True
    rhino.round_state.remained_stationary_this_round = False

    _disembark_by_decision(game, marine_player, tactical_squad, rhino)

    assert tactical_squad.round_state.disembarked_from_moved_transport is True
    assert tactical_squad.round_state.moved_this_round is True
    assert tactical_squad.round_state.remained_stationary_this_round is False
    assert tactical_squad.round_state.disembarked_cannot_charge is True
    assert tactical_squad.can_declare_charge_against(boyz, game) is False
    assert (
        build_select_movement_action_request(
            tactical_squad,
            player_id=marine_player.id,
            phase_name="MOVEMENT_PHASE",
            phase_step="MOVE_UNITS",
            game_map=game.map,
        )
        is None
    )


def test_core_advance_or_fall_back_blocks_voluntary_disembark_but_destroyed_transport_forces_it() -> None:
    game, _marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)
    rhino.round_state.moved_this_round = True
    rhino.round_state.remained_stationary_this_round = False
    rhino.round_state.advanced_this_round = True

    assert tactical_squad.disembark(game_map=game.map, transport_unit=rhino, current_turn=1) is False
    assert tactical_squad.embarked_in is rhino

    game, _marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)
    rhino.round_state.moved_this_round = True
    rhino.round_state.remained_stationary_this_round = False
    rhino.round_state.fell_back_this_round = True

    assert tactical_squad.disembark(game_map=game.map, transport_unit=rhino, current_turn=1) is False
    assert tactical_squad.embarked_in is rhino

    game, _marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)
    rhino.round_state.moved_this_round = True
    rhino.round_state.remained_stationary_this_round = False
    rhino.round_state.advanced_this_round = True
    rhino.round_state.fell_back_this_round = True

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=6):
        assert tactical_squad.disembark(
            game_map=game.map,
            transport_unit=rhino,
            destroyed_transport=True,
            current_turn=1,
        ) is True

    assert tactical_squad.embarked_in is None
    assert tactical_squad.round_state.disembarked_from_destroyed_transport is True
    assert tactical_squad.round_state.disembarked_cannot_charge is True
    assert tactical_squad.round_state.moved_this_round is True
    assert tactical_squad.is_battle_shocked() is True


def test_core_destroyed_transport_emergency_disembark_fallback_uses_real_wahapedia_models() -> None:
    game, _marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)
    emergency_positions = _find_disembark_positions(game, tactical_squad, rhino, max_distance=6.0)

    with patch.object(
        tactical_squad,
        "_find_disembark_positions",
        side_effect=[None, emergency_positions],
    ) as find_positions, patch("warhammer40k_ai.units.unit.get_roll", return_value=6):
        assert tactical_squad.disembark(
            game_map=game.map,
            transport_unit=rhino,
            destroyed_transport=True,
            emergency=False,
            current_turn=1,
        ) is True

    assert tactical_squad.embarked_in is None
    assert tactical_squad.round_state.disembarked_from_destroyed_transport is True
    assert tactical_squad.round_state.disembarked_cannot_charge is True
    assert find_positions.call_count == 2
    assert find_positions.call_args_list[0].kwargs["max_distance"] == 3.0
    assert find_positions.call_args_list[1].kwargs["max_distance"] == 6.0


def test_headless_policy_receives_movement_phase_disembark_choice_with_real_wahapedia_transport() -> None:
    game, marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _start_embarked(rhino, tactical_squad, game)
    router = _RecordingTransportRouter(preferred_actions=("disembark",))
    HeadlessPolicyDecisionController(
        game=game,
        ai_router=router,
        skip_decision_types={DECISION_SELECT_UNIT, DECISION_SELECT_MOVEMENT_ACTION, DECISION_MOVE_UNIT},
        auto_attach=True,
    )

    pending_transport_choice = game._queue_movement_phase_start_transport_choices(player=marine_player)

    assert pending_transport_choice is False
    disembark_requests = router.requests_of_type(DECISION_DISEMBARK)
    assert len(disembark_requests) == 1
    request = disembark_requests[0]
    candidate_actions = {str(candidate.params.get("action", "") or "") for candidate in request.candidates}
    assert {"skip", "disembark"}.issubset(candidate_actions)
    disembark_candidates = [
        candidate for candidate in request.candidates if str(candidate.params.get("action", "") or "") == "disembark"
    ]
    assert len(disembark_candidates) == 1
    assert disembark_candidates[0].params["unit_id"] == get_entity_id(tactical_squad)
    assert disembark_candidates[0].params["transport_id"] == get_entity_id(rhino)
    assert tactical_squad.embarked_in is None
    assert tactical_squad in game.map.units
    assert tactical_squad.round_state.disembarked_this_round is True


def test_headless_policy_receives_movement_phase_embark_choice_after_real_move_with_wahapedia_models() -> None:
    game, marine_player, rhino, tactical_squad, _boyz = _core_fixture()
    _place_unit_grid(game, tactical_squad, 5.0, 5.0)
    final_positions = _find_disembark_positions(game, tactical_squad, rhino)
    router = _RecordingTransportRouter(preferred_actions=("embark",))
    HeadlessPolicyDecisionController(
        game=game,
        ai_router=router,
        skip_decision_types={DECISION_SELECT_UNIT, DECISION_SELECT_MOVEMENT_ACTION, DECISION_MOVE_UNIT},
        auto_attach=True,
    )

    _move_unit_by_decision(game, marine_player, tactical_squad, final_positions)

    embark_requests = router.requests_of_type(DECISION_EMBARK)
    assert len(embark_requests) == 1
    request = embark_requests[0]
    candidate_actions = {str(candidate.params.get("action", "") or "") for candidate in request.candidates}
    assert {"skip", "embark"}.issubset(candidate_actions)
    embark_candidates = [
        candidate for candidate in request.candidates if str(candidate.params.get("action", "") or "") == "embark"
    ]
    assert len(embark_candidates) == 1
    assert embark_candidates[0].params["unit_id"] == get_entity_id(tactical_squad)
    assert embark_candidates[0].params["transport_id"] == get_entity_id(rhino)
    assert tactical_squad.embarked_in is rhino
    assert tactical_squad not in game.map.units
    assert tactical_squad.round_state.embarked_this_round is True
