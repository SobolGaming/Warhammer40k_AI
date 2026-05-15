from types import SimpleNamespace

from warhammer40k_ai.engine.game_mixins.phase_handlers_mixin import GamePhaseHandlersMixin


class _MovementPhaseGame(GamePhaseHandlersMixin):
    pass


def test_movement_phase_disembark_availability_reuses_position_search_until_map_changes() -> None:
    game = _MovementPhaseGame()
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.turn = 1
    game.map = SimpleNamespace(state_generation=7, units=[])

    transport_base = SimpleNamespace(x=10.0, y=12.0, z=0.0, facing=0.0)
    transport_model = SimpleNamespace(id="model:transport", is_alive=True, model_base=transport_base)
    passenger_model = SimpleNamespace(id="model:passenger", is_alive=True, model_base=SimpleNamespace())
    transport = SimpleNamespace(
        id="unit:transport",
        name="Transport",
        is_transport=True,
        is_embarked=False,
        embarked_in=None,
        deployed=True,
        models=[transport_model],
        transport_passengers=[],
        round_state=SimpleNamespace(advanced_this_round=False, fell_back_this_round=False),
        is_alive=lambda: True,
    )
    passenger = SimpleNamespace(
        id="unit:passenger",
        name="Passenger",
        embarked_in=transport,
        deployed=False,
        models=[passenger_model],
        round_state=SimpleNamespace(embarked_this_round=False, disembarked_this_round=False),
        is_alive=lambda: True,
    )
    transport.transport_passengers = [passenger]
    game.map.units = [transport]

    calls = []

    def _find_positions(*, transport_base, game_map, max_distance):
        calls.append((transport_base, game_map, max_distance))
        return [(11.0, 12.0, 0.0, 0.0)]

    passenger._find_disembark_positions = _find_positions

    assert game._movement_phase_can_voluntarily_disembark(passenger, transport) is True
    assert game._movement_phase_can_voluntarily_disembark(passenger, transport) is True
    assert len(calls) == 1

    game.map.state_generation += 1

    assert game._movement_phase_can_voluntarily_disembark(passenger, transport) is True
    assert len(calls) == 2

