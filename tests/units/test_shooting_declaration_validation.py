from types import SimpleNamespace

from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType


def _model(name: str = "Shooter") -> Model:
    return Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )


def _ranged_weapon(name: str) -> Wargear:
    return Wargear(
        {
            "name": name,
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


def _unit_with_model(model: Model, army: object) -> Unit:
    unit = Unit.__new__(Unit)
    unit.name = "Shooter Unit"
    unit.models = [model]
    unit.round_state = SimpleNamespace(advanced_this_round=False, fell_back_this_round=False)
    unit.get_parent_army = lambda: army
    unit._can_model_shoot_weapon_at_target = lambda *args, **kwargs: True
    model.parent_unit = unit
    return unit


def test_model_has_weapon_profile_matches_equivalent_model_local_weapon_profile():
    model = _model()
    carried_weapon = _ranged_weapon("Bolt rifle")
    selected_weapon = _ranged_weapon("Bolt rifle")
    model.wargear = [carried_weapon]

    unit = _unit_with_model(model, SimpleNamespace(player=SimpleNamespace(game=None)))

    assert carried_weapon.id != selected_weapon.id
    assert unit._model_has_weapon_profile(model, selected_weapon.profiles["default"])


def test_validate_shooting_declaration_rejects_model_without_selected_weapon():
    model = _model()
    model.wargear = [_ranged_weapon("Bolt rifle")]
    selected_weapon = _ranged_weapon("Missile launcher")
    selected_profile = selected_weapon.profiles["default"]

    shooter_army = SimpleNamespace(id="shooter", player=SimpleNamespace(game=None))
    target_army = SimpleNamespace(id="target", player=SimpleNamespace(game=None))
    unit = _unit_with_model(model, shooter_army)
    target = SimpleNamespace(
        name="Target",
        get_parent_army=lambda: target_army,
        is_alive=lambda: True,
    )

    result = unit._validate_shooting_declaration(selected_profile, target, [model], object())

    assert result == {"valid": False, "reason": "No models in range or line of sight"}
