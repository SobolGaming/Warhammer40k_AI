import pytest

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.decision_port import DecisionPort
from warhammer40k_ai.engine.game import Battlefield, Game


def _provider(**_kwargs):
    return "use"


def test_game_decision_providers_are_installed_on_decision_port_only():
    game = Game(Battlefield(width=60, height=44))

    game.install_decision_providers(damage_allocation_provider=_provider)

    assert game.decision_port.get_provider("damage_allocation_provider") is _provider
    with pytest.raises(AttributeError, match="Game.decision_port"):
        _ = game.map.damage_allocation_provider


def test_map_provider_assignment_is_rejected():
    game = Game(Battlefield(width=60, height=44))

    with pytest.raises(AttributeError, match="Game.decision_port"):
        game.map.model_allocated_damage_zero_provider = _provider

    assert game.decision_port.get_provider("model_allocated_damage_zero_provider") is None


def test_standalone_map_provider_assignment_is_rejected():
    replacement = Map(width=44, height=30)

    with pytest.raises(AttributeError, match="Game.decision_port"):
        replacement.miracle_dice_provider = _provider


def test_decision_port_rejects_unknown_provider_name():
    port = DecisionPort()

    try:
        port.set_provider("unknown_provider", _provider)
    except ValueError as exc:
        assert "Unknown decision provider" in str(exc)
    else:
        raise AssertionError("Unknown decision provider was accepted.")
