from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_model(name: str) -> Model:
    return Model(
        name=name,
        movement=8,
        toughness=4,
        save=4,
        wounds=3,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1),
    )


def test_anchorite_sarcophagus_applies_move_and_save_to_bearer_only():
    unit = Unit.__new__(Unit)
    unit.possible_wargear = []
    unit.possible_abilities = [
        Ability(
            "Anchorite Sarcophagus",
            "",
            'The bearer has a Move characteristic of 7" and a Save characteristic of 3+.',
            "Wargear",
            "",
        )
    ]
    unit._ability_cache = {}

    bearer = _make_model("Anchorite")
    other = _make_model("Mortifier")
    bearer.optional_wargear.append("Anchorite Sarcophagus")

    bearer.set_parent_unit(unit)
    other.set_parent_unit(unit)
    unit.models = [bearer, other]

    move_bearer, move_source = unit.get_model_move_characteristic_override(bearer)
    move_other, _ = unit.get_model_move_characteristic_override(other)
    save_bearer, save_source = unit.get_model_save_characteristic_override(bearer)
    save_other, _ = unit.get_model_save_characteristic_override(other)

    assert move_bearer == 7
    assert move_other is None
    assert save_bearer == 3
    assert save_other is None
    assert move_source == "Anchorite Sarcophagus"
    assert save_source == "Anchorite Sarcophagus"
