from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.utility.model_base import Base, BaseType


class _DummyPlayer:
    def __init__(self, name: str = "P1"):
        self.name = name
        self.game = None


class MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "5", "Sv": "3", "W": "2",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def build_model(name: str, toughness: int) -> Model:
    return Model(
        name=name,
        movement=6,
        toughness=toughness,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )


def make_support_weapon_unit(name: str, model_toughness: int, model_count: int) -> Unit:
    abilities = [{
        "name": "Support Weapon",
        "description": (
            "Each time an attack targets this model's unit, if that unit contains one or more other models, "
            "until that attack is resolved, this model has a Toughness characteristic of 3."
        ),
        "type": "",
        "parameter": "",
    }]
    datasheet = MockDatasheet(name, abilities=abilities)
    unit = Unit(datasheet)
    models = []
    for i in range(model_count):
        model = build_model(f"{name} {i+1}", model_toughness)
        model.parent_unit = unit
        models.append(model)
    unit.models = models
    return unit


def make_support_weapon_artillery_unit(name: str, model_toughness: int) -> Unit:
    abilities = [
        {
            "name": "Support Weapon",
            "description": (
                "Each time an attack targets this model's unit, if that unit contains one or more other models, "
                "until that attack is resolved, this model has a Toughness characteristic of 3."
            ),
            "type": "",
            "parameter": "",
        },
        {
            "name": "Support Artillery",
            "description": (
                "At the start of the Declare Battle Formations step, this model can join one Guardian Defenders unit from your army "
                "(a unit cannot have more than one Support Weapon model joined to it)."
            ),
            "type": "",
            "parameter": "",
        },
    ]
    datasheet = MockDatasheet(name, abilities=abilities)
    unit = Unit(datasheet)
    model = build_model(f"{name} 1", model_toughness)
    model.parent_unit = unit
    unit.models = [model]
    return unit


def make_guardian_unit(model_toughness: int) -> Unit:
    datasheet = MockDatasheet("Guardian Defenders")
    unit = Unit(datasheet)
    model = build_model("Guardian Defender", model_toughness)
    model.parent_unit = unit
    unit.models = [model]
    return unit


def _make_army(units):
    army = Army.with_detachment(faction="Test", detachment_type="Test", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for u in army.units:
        u.parent_army = army
    return army


def _attack_profile():
    parent_wargear = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent_wargear,
    )


def _attack_with_profile(target_unit, attacker_model):
    from warhammer40k_ai.units import wargear as wargear_mod
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _s: 6
    try:
        return _attack_profile().attack(target_unit, attacker_model)
    finally:
        wargear_mod.get_roll = old_get_roll


def test_support_weapon_toughness_override_when_other_models_present():
    target = make_support_weapon_unit("Support Weapon", model_toughness=5, model_count=2)

    attacker_ds = MockDatasheet("Attacker")
    attacker_unit = Unit(attacker_ds)
    attacker_model = build_model("Attacker", 4)
    attacker_model.parent_unit = attacker_unit

    result = _attack_with_profile(target, attacker_model)
    assert result.wound_results
    assert result.wound_results[0]["target_toughness"] == 3


def test_support_weapon_toughness_no_override_for_single_model():
    target = make_support_weapon_unit("Support Weapon", model_toughness=5, model_count=1)

    attacker_ds = MockDatasheet("Attacker")
    attacker_unit = Unit(attacker_ds)
    attacker_model = build_model("Attacker", 4)
    attacker_model.parent_unit = attacker_unit

    result = _attack_with_profile(target, attacker_model)
    assert result.wound_results
    assert result.wound_results[0]["target_toughness"] == 5


def test_support_weapon_toughness_override_when_joined_to_guardians():
    support = make_support_weapon_artillery_unit("Support Weapon Platform", model_toughness=5)
    guardian = make_guardian_unit(model_toughness=4)
    _make_army([support, guardian])

    support.attach_support_artillery_to(guardian)
    assert support.toughness == 3

    guardian.models[0].wounds = 0
    assert support.toughness == 5
