from __future__ import annotations

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
    ) as find_positions, patch.object(game.map, "place_unit", side_effect=[False, True]) as place_unit:
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
