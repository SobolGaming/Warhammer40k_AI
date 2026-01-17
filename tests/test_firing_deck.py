import types

from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


def _mk_model(name: str) -> Model:
    base = Base(BaseType.CIRCULAR, 1.0)
    return Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=base,
    )


def test_apply_and_clear_firing_deck_virtual_wargear_injects_into_transport_model():
    transport = Unit.__new__(Unit)
    transport.models = [_mk_model("Transport")]
    transport.models[0].wargear = []

    passenger = _mk_model("Passenger")
    passenger_wg = Wargear(
        {
            "name": "Lasgun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    passenger.wargear = [passenger_wg]

    selection = {
        "model": passenger,
        "wargear": passenger_wg,
        "profile": passenger_wg.profiles["default"],
        "profile_name": "default",
    }

    transport.apply_firing_deck_virtual_wargear([selection])

    # Injected wargear exists on transport model
    assert len(transport.models[0].wargear) == 1
    assert getattr(transport, "_firing_deck_virtual_wargear")
    assert getattr(transport, "_firing_deck_virtual_sources")
    # Mapping points back to the passenger model
    assert passenger in list(transport._firing_deck_virtual_sources.values())[0]

    transport.clear_firing_deck_virtual_wargear()
    assert len(transport.models[0].wargear) == 0
    assert transport._firing_deck_virtual_wargear == []
    assert transport._firing_deck_virtual_sources == {}


def test_firing_deck_marks_source_models_as_shot_during_execute():
    # Minimal Unit object (avoid heavy datasheet construction)
    shooter = Unit.__new__(Unit)
    shooter.name = "Shooter"
    shooter.has_keyword = lambda _kw: False
    shooter.models = [_mk_model("ShooterModel")]
    shooter.round_state = types.SimpleNamespace(
        action_locked_until_turn_end=False,
        shot_this_round=False,
        fell_back_this_round=False,
        advanced_this_round=False,
    )

    # Validation always fails so we don't need a real map/target resolution
    shooter._validate_shooting_declaration = lambda *args, **kwargs: {"valid": False, "reason": "skip"}

    # Build a real profile object for pistol checks / naming
    wg = Wargear(
        {
            "name": "Bolter",
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = wg.profiles["default"]

    passenger_unit = types.SimpleNamespace(round_state=types.SimpleNamespace(shot_this_round=False))
    passenger_model = _mk_model("Passenger")
    passenger_model.parent_unit = passenger_unit

    target_unit = types.SimpleNamespace(is_alive=lambda: True)
    decls = [
        {
            "weapon_profile": profile,
            "target_unit": target_unit,
            "models": [shooter.models[0]],
            "firing_deck_source_models": [passenger_model],
        }
    ]

    shooter.execute_shooting_declarations(decls, game_map=object())

    assert shooter.round_state.shot_this_round is True
    assert getattr(passenger_model, "_shot_via_firing_deck_this_round") is True
    assert passenger_unit.round_state.shot_this_round is True


