from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, faction_name="Chaos Daemons"):
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
    return Unit(_MockDatasheet(name, abilities=abilities))


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


def _make_melee_profile():
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
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


def _make_target():
    return SimpleNamespace(
        toughness=4,
        models=[SimpleNamespace(is_alive=True)],
        has_keyword=lambda _k: False,
        is_vehicle=False,
        is_monster=False,
    )


def test_critical_hit_on_charge_applies():
    ability = {
        "name": "Relentless Onslaught",
        "description": (
            "Each time a model in this unit makes a melee attack, if it made a Charge move this turn, "
            "an unmodified Hit roll of 5+ scores a Critical Hit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit("Test Unit", abilities=[ability])
    unit.round_state.charged_this_round = True

    profile = _make_melee_profile()
    target = _make_target()
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        hit_result = profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

    assert hit_result.get("crit_threshold") == 5
    assert attack_instance.get("crit_hit") is True


def test_critical_hit_on_charge_not_applied_without_charge():
    ability = {
        "name": "Relentless Onslaught",
        "description": (
            "Each time a model in this unit makes a melee attack, if it made a Charge move this turn, "
            "an unmodified Hit roll of 5+ scores a Critical Hit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit("Test Unit", abilities=[ability])
    unit.round_state.charged_this_round = False

    profile = _make_melee_profile()
    target = _make_target()
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        hit_result = profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

    assert hit_result.get("crit_threshold") == 6
    assert not attack_instance.get("crit_hit", False)
