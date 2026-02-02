from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, model_count=1, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "4", "W": "2",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, *, model_count=1, abilities=None) -> Unit:
    datasheet = MockDatasheet(name, model_count=model_count, abilities=abilities)
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def test_model_hit_bonus_applies_vs_below_half_strength_target():
    ability_text = (
        "Each time this model makes an attack that targets a unit below half-strength, "
        "add 1 to the Hit roll."
    )
    abilities = [{
        "name": "Cull the Weak",
        "description": ability_text,
        "type": "Datasheet",
        "parameter": "",
    }]

    attacker = _make_unit("Attacker", model_count=1, abilities=abilities)
    target = _make_unit("Target", model_count=3)
    target.models = target.models[:1]

    mods = attacker.model_attack_roll_modifiers_vs_weakened_target(
        attacker.models[0],
        attack_type="ranged",
        target=target,
    )

    assert mods.get("hit") == 1
    assert "below Half-strength" in " ".join(mods.get("hit_reasons", ()))


def test_model_hit_bonus_not_applied_vs_not_below_half_strength_target():
    ability_text = (
        "Each time this model makes an attack that targets a unit below half-strength, "
        "add 1 to the Hit roll."
    )
    abilities = [{
        "name": "Cull the Weak",
        "description": ability_text,
        "type": "Datasheet",
        "parameter": "",
    }]

    attacker = _make_unit("Attacker", model_count=1, abilities=abilities)
    target = _make_unit("Target", model_count=3)
    target.models = target.models[:2]

    mods = attacker.model_attack_roll_modifiers_vs_weakened_target(
        attacker.models[0],
        attack_type="ranged",
        target=target,
    )

    assert mods.get("hit") == 0
