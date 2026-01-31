from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


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


def test_enemy_melee_weapons_hazardous_targeting(monkeypatch):
    import warhammer40k_ai.units.wargear as wargear_module

    ability = {
        "name": "Treacherous Illusion (Psychic)",
        "description": "Melee weapons equipped by enemy models have the [HAZARDOUS] ability while targeting this model's unit.",
        "type": "Datasheet",
        "parameter": "",
    }
    target_unit = _make_unit("Target", abilities=[ability])
    attacker_unit = _make_unit("Attacker")
    attacker_model = attacker_unit.models[0]

    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    profile = WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )

    monkeypatch.setattr(wargear_module, "get_roll", lambda _dice: 1)
    result = profile.attack(target_unit, attacker_model)

    assert result is not None
    assert result.hazardous_roll == 1
    assert result.hazardous_damage == 3
