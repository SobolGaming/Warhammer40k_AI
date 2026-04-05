from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        faction_name="Chaos Daemons",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = [faction_name.upper()]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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
        self.attached_to = []


def _make_unit(name, *, abilities=None):
    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def test_bearer_melee_weapons_lance_applies():
    ability = {
        "name": "Grav-talon",
        "description": "The bearer's melee weapons have the [LANCE] ability.",
        "type": "Wargear",
        "parameter": "",
    }
    unit = _make_unit("Test", abilities=[ability])
    unit.models[0].optional_wargear.append("Grav-talon")
    unit.round_state.charged_this_round = True

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
    target = SimpleNamespace(
        toughness=4,
        models=[SimpleNamespace(is_alive=True)],
        has_keyword=lambda _k: False,
        is_vehicle=False,
        is_monster=False,
    )
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 3]):
        profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
        wound_result = profile._wound_target_with_tracking(target, unit.models[0], attack_instance)

    assert wound_result.get("wound") is True
