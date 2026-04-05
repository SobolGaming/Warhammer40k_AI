from types import SimpleNamespace

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


def _make_profile():
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


def _make_target_unit():
    return SimpleNamespace(
        toughness=5,
        models=[SimpleNamespace(is_alive=True)],
        has_keyword=lambda _k: False,
        is_vehicle=False,
        is_monster=False,
    )


def _make_target_model():
    return SimpleNamespace(
        name="Target",
        wounds=5,
        is_alive=True,
        parent_unit=None,
    )


def test_charge_melee_strength_damage_bonus_applies_on_charge():
    ability = {
        "name": "Thunderous Impact",
        "description": "Each time a model in this unit makes a melee attack, if this unit made a Charge move this turn, improve the Strength and Damage characteristics of that attack by 1.",
        "type": "Ability",
        "parameter": "",
    }
    unit = _make_unit("Test", abilities=[ability])
    unit.round_state.charged_this_round = True

    profile = _make_profile()
    target_unit = _make_target_unit()

    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        target_unit,
        unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result.get("wound") is True

    damage_instance = {"_aura_attack_mods": _aura_stub()}
    damage_result = profile._damage_target_with_tracking(
        _make_target_model(),
        unit.models[0],
        damage_instance,
        allow_rerolls=False,
    )

    assert damage_result.get("damage_applied") == 2


def test_charge_melee_strength_damage_bonus_not_applied_without_charge():
    ability = {
        "name": "Cutting Down the Foe",
        "description": "Each time a model in this unit makes a melee attack, if this unit made a Charge move this turn, improve the Strength and Damage characteristics of that attack by 1.",
        "type": "Ability",
        "parameter": "",
    }
    unit = _make_unit("Test", abilities=[ability])
    unit.round_state.charged_this_round = False

    profile = _make_profile()
    target_unit = _make_target_unit()

    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        target_unit,
        unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result.get("wound") is False

    damage_instance = {"_aura_attack_mods": _aura_stub()}
    damage_result = profile._damage_target_with_tracking(
        _make_target_model(),
        unit.models[0],
        damage_instance,
        allow_rerolls=False,
    )

    assert damage_result.get("damage_applied") == 1
