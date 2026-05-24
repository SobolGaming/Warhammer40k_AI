from __future__ import annotations

import logging
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, transport=""):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport


def _make_unit(name, *, abilities=None, keywords=None, transport=""):
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            transport=transport,
        )
    )


def test_destroyed_transport_disembark_retries_as_emergency_after_final_validation_failure():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army = Army.with_detachment("Test", "Detachment")
    player = Player("P1", PlayerControl.LOCAL, army)
    game = Game(bf, players=[player])

    transport = _make_unit("Transport", keywords=["Transport"], transport="Transport Capacity 10")
    passenger = _make_unit("Passengers", keywords=["Infantry"])

    army.add_unit(transport)
    army.add_unit(passenger)
    game.rebuild_entity_registry()

    transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    assert game.map.place_unit(transport) is True

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport

    normal_positions = [(12.5, 10.0, 0.0, 0.0)]
    emergency_positions = [(14.5, 10.0, 0.0, 0.0)]

    with patch.object(
        passenger,
        "_find_disembark_positions",
        side_effect=[normal_positions, emergency_positions],
    ) as find_positions, patch.object(game.map, "place_unit", side_effect=[False, True]) as place_unit, patch(
        "warhammer40k_ai.units.unit.get_roll",
        return_value=4,
    ) as roll_mock:
        ok = passenger.disembark(
            game_map=game.map,
            transport_unit=transport,
            destroyed_transport=True,
            emergency=False,
            current_turn=1,
        )

    assert ok is True
    assert passenger.embarked_in is None
    assert transport.transport_passengers == []
    assert passenger.round_state.disembarked_this_round is True
    assert passenger.round_state.disembarked_from_destroyed_transport is True
    assert place_unit.call_count == 2
    assert find_positions.call_count == 2
    assert find_positions.call_args_list[0].kwargs["max_distance"] == 3.0
    assert find_positions.call_args_list[1].kwargs["max_distance"] == 6.0
    assert roll_mock.call_args.kwargs["player"] is player
    assert roll_mock.call_args.kwargs["roll_type"] == "destroyed_transport_disembark"
    assert (
        roll_mock.call_args.kwargs["reason"]
        == "Destroyed Transport disembark casualty roll for Passengers Test Model from Transport"
    )


def test_normal_disembark_final_validation_failure_logs_warning_not_error(caplog):
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army = Army.with_detachment("Test", "Detachment")
    player = Player("P1", PlayerControl.LOCAL, army)
    game = Game(bf, players=[player])

    transport = _make_unit("Transport", keywords=["Transport"], transport="Transport Capacity 10")
    passenger = _make_unit("Passengers", keywords=["Infantry"])

    army.add_unit(transport)
    army.add_unit(passenger)
    game.rebuild_entity_registry()

    transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    assert game.map.place_unit(transport) is True

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport

    with (
        patch.object(passenger, "_find_disembark_positions", return_value=[(12.5, 10.0, 0.0, 0.0)]),
        patch.object(game.map, "place_unit", return_value=False),
        caplog.at_level(logging.WARNING),
    ):
        ok = passenger.disembark(
            game_map=game.map,
            transport_unit=transport,
            destroyed_transport=False,
            emergency=False,
            current_turn=1,
        )

    assert ok is False
    assert "WARN: Passengers disembark failed: map placement validation failed" in caplog.text
    assert "ERROR: Passengers disembark failed: map placement validation failed" not in caplog.text


def test_normal_disembark_places_attached_leader_collision_models():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army = Army.with_detachment("Test", "Detachment")
    player = Player("P1", PlayerControl.LOCAL, army)
    game = Game(bf, players=[player])

    transport = _make_unit("Transport", keywords=["Transport"], transport="Transport Capacity 10")
    passenger = _make_unit("Passengers", keywords=["Infantry"])
    leader = _make_unit("Leader", keywords=["Character", "Infantry"])

    passenger.attached_leaders = [leader]
    leader.attached_to = passenger

    army.add_unit(transport)
    army.add_unit(passenger)
    army.add_unit(leader)
    game.rebuild_entity_registry()

    transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    assert game.map.place_unit(transport) is True

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport
    leader.embarked_in = transport

    placements = passenger._find_disembark_positions(transport.models[0].model_base, game.map, 3.0)
    assert placements is not None
    assert len(placements) == 2

    ok = passenger.disembark(
        game_map=game.map,
        transport_unit=transport,
        destroyed_transport=False,
        emergency=False,
        current_turn=1,
    )

    assert ok is True
    assert passenger.embarked_in is None
    assert leader.embarked_in is None
    assert transport.transport_passengers == []
    assert passenger in game.map.units
    assert leader not in game.map.units
    for model in passenger.get_models_for_collision():
        x, y, _z, _facing = model.get_location()
        assert (round(x, 3), round(y, 3)) != (0.0, 0.0)


def test_finalize_manual_disembark_final_validation_failure_logs_warning_not_error(caplog):
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    army = Army.with_detachment("Test", "Detachment")
    player = Player("P1", PlayerControl.LOCAL, army)
    game = Game(bf, players=[player])

    transport = _make_unit("Transport", keywords=["Transport"], transport="Transport Capacity 10")
    passenger = _make_unit("Passengers", keywords=["Infantry"])

    army.add_unit(transport)
    army.add_unit(passenger)
    game.rebuild_entity_registry()

    transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    assert game.map.place_unit(transport) is True

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport
    passenger.models[0].set_location(12.5, 10.0, 0.0, 0.0)

    with patch.object(game.map, "place_unit", return_value=False), caplog.at_level(logging.WARNING):
        ok = passenger.finalize_manual_disembark(
            game_map=game.map,
            transport_unit=transport,
            destroyed_transport=False,
            emergency=False,
            current_turn=1,
        )

    assert ok is False
    assert "WARN: Passengers disembark failed: map placement validation failed" in caplog.text
    assert "ERROR: Passengers disembark failed: map placement validation failed" not in caplog.text
