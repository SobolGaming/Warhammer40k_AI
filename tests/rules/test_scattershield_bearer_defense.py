from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_model(name: str, save: int) -> Model:
    return Model(
        name=name,
        movement=6,
        toughness=4,
        save=save,
        wounds=3,
        leadership=6,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1),
    )


def _make_scattershield_unit() -> Unit:
    unit = Unit.__new__(Unit)
    unit.possible_wargear = []
    unit.possible_abilities = [
        Ability(
            "Scattershield",
            "",
            "The bearer has a 4+ invulnerable save and each time an attack is allocated to the bearer, subtract 1 from the Damage characteristic of that attack.",
            "Wargear",
            "",
        )
    ]
    unit._ability_cache = {}
    return unit


def test_scattershield_bearer_invuln_and_damage_reduction():
    unit = _make_scattershield_unit()
    model = _make_model("Bearer", save=5)
    model.optional_wargear.append("Scattershield")
    model.set_parent_unit(unit)
    unit.models = [model]

    save_profile = WargearProfile(
        "default",
        {
            "name": "Test Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
    )
    save_result = save_profile._save_with_tracking(
        model,
        {"weapon_profile": save_profile, "is_mortal": False},
        ap=0,
    )
    assert save_result["final_save"] == 4

    attacker_unit = Unit.__new__(Unit)
    attacker_model = _make_model("Attacker", save=6)
    attacker_model.set_parent_unit(attacker_unit)
    attacker_unit.models = [attacker_model]

    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    damage_profile = WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )
    attack_instance = {"mortal_wound": False, "mortal_wound_in_addition": False}
    damage_result = damage_profile._damage_target_with_tracking(model, attacker_model, attack_instance)
    assert damage_result["damage_applied"] == 1
