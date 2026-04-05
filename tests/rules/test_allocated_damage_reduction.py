from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name, *, abilities=None):
    return Unit(_MockDatasheet(name, abilities=abilities))


def test_allocated_damage_reduction_applies():
    from types import SimpleNamespace
    from warhammer40k_ai.units.wargear import WargearProfile

    ability = {
        "name": "Staunch",
        "description": "Each time an attack is allocated to this model, subtract 1 from the Damage characteristic of that attack.",
        "type": "Datasheet",
        "parameter": "",
    }
    target_unit = _make_unit("Target", abilities=[ability])
    attacker_unit = _make_unit("Attacker")

    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    profile = WargearProfile(
        profile_name="Melee",
        wargear_data={
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
    result = profile._damage_target_with_tracking(target_unit.models[0], attacker_unit.models[0], attack_instance)
    assert result["damage_applied"] == 1


def test_allocated_damage_halving_rounds_up():
    from types import SimpleNamespace
    from warhammer40k_ai.units.wargear import WargearProfile

    ability = {
        "name": "Stoic Endurance",
        "description": "Each time an attack is allocated to this model, halve the Damage characteristic of that attack.",
        "type": "Datasheet",
        "parameter": "",
    }
    target_unit = _make_unit("Target", abilities=[ability])
    attacker_unit = _make_unit("Attacker")

    parent = SimpleNamespace(name="Heavy Blade", is_melee=lambda: True, is_ranged=lambda: False)
    profile = WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "5",
            "description": "",
        },
        parent_wargear=parent,
    )

    attack_instance = {"mortal_wound": False, "mortal_wound_in_addition": False}
    result = profile._damage_target_with_tracking(target_unit.models[0], attacker_unit.models[0], attack_instance)
    assert result["damage_applied"] == 3
