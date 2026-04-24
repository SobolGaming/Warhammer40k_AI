from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.decision_port import DecisionPort
from warhammer40k_ai.engine.game import Battlefield, Game


def _provider(**_kwargs):
    return "use"


def test_game_decision_port_is_visible_through_map_compat_accessor():
    game = Game(Battlefield(width=60, height=44))

    game.install_decision_providers(damage_allocation_provider=_provider)

    assert game.decision_port.get_provider("damage_allocation_provider") is _provider
    assert game.map.damage_allocation_provider is _provider


def test_map_provider_assignment_updates_game_decision_port():
    game = Game(Battlefield(width=60, height=44))

    game.map.model_allocated_damage_zero_provider = _provider

    assert game.decision_port.get_provider("model_allocated_damage_zero_provider") is _provider


def test_standalone_map_provider_overrides_transfer_when_attached_to_game():
    replacement = Map(width=44, height=30)
    replacement.miracle_dice_provider = _provider
    game = Game(Battlefield(width=60, height=44))

    game.set_map(replacement)

    assert game.decision_port.get_provider("miracle_dice_provider") is _provider
    assert replacement.miracle_dice_provider is _provider


def test_roll_reroll_fallback_uses_decision_port_provider():
    game = Game(Battlefield(width=60, height=44))
    game.install_decision_providers(roll_reroll_provider=lambda **_kwargs: True)

    assert game.map._fallback_roll_reroll_choice(allow_reroll=True) is True


def test_decision_port_rejects_unknown_provider_name():
    port = DecisionPort()

    try:
        port.set_provider("unknown_provider", _provider)
    except ValueError as exc:
        assert "Unknown decision provider" in str(exc)
    else:
        raise AssertionError("Unknown decision provider was accepted.")
