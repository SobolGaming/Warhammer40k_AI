import warhammer40k_ai.classes.model as model_module
from warhammer40k_ai.classes.unit import Unit


class MockDatasheet:
    def __init__(self):
        self.name = "Psychic Target"
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "2",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [{
            "name": "Psychic Ward",
            "description": "The bearer has the Feel No Pain 5+ ability against Psychic attacks.",
            "type": "Datasheet",
            "parameter": "",
        }]
        self.loadout = "This model is equipped with: nothing"


def test_psychic_mortal_wounds_trigger_fnp(monkeypatch):
    monkeypatch.setattr(model_module, "get_roll", lambda *_args, **_kwargs: 6)
    unit = Unit(MockDatasheet())
    model = unit.models[0]
    start_wounds = model.wounds
    model.take_damage(1, is_mortal=True, weapon_profile=None, is_psychic_attack=True)
    assert model.wounds == start_wounds
