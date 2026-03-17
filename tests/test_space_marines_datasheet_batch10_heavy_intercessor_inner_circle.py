from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


class _RangedWargear:
    name = "Test Gun"

    def is_ranged(self):
        return True

    def is_melee(self):
        return False


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


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


def test_heavy_intercessor_unyielding_requires_controlled_objective():
    heavy_intercessors = _actual_unit("Heavy Intercessor Squad", datasheet_id="000001177")
    heavy_intercessors._parse_against_attack_characteristic_defensive_rules()
    entries = list(
        getattr(heavy_intercessors, "special_rules", {}).get("armor_save_bonus_vs_damage_characteristic_entries", [])
        or []
    )
    assert len(entries) == 1
    assert bool(entries[0].get("requires_objective_controlled")) is True

    profile = WargearProfile(
        "Test Gun",
        {"range": "24", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1", "description": ""},
        parent_wargear=_RangedWargear(),
    )
    target_model = heavy_intercessors.models[0]

    heavy_intercessors._within_controlled_objective_range = lambda game_map=None: False
    failed_save = profile._save_with_tracking(
        target_model,
        {},
        ap=0,
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert failed_save["saved"] is False
    assert not any("Unyielding in the Face of the Foe" in effect for effect in failed_save["special_effects"])

    heavy_intercessors._within_controlled_objective_range = lambda game_map=None: True
    successful_save = profile._save_with_tracking(
        target_model,
        {},
        ap=0,
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert successful_save["saved"] is True
    assert any("Unyielding in the Face of the Foe" in effect for effect in successful_save["special_effects"])


def test_inner_circle_braziers_applies_only_while_led_by_character():
    inner_circle = _actual_unit("Inner Circle Companions", datasheet_id="000003698")
    attacker = _mock_unit("Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    leader = _mock_unit(
        "Leader",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    attack_profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_RangedWargear(),
    )

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
        no_leader_result = attack_profile._hit_target_with_tracking(
            inner_circle,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    assert no_leader_result["hit"] is True

    army = Army("Space Marines", detachment_type="Other")
    army.faction_id = "SM"
    army.add_unit(inner_circle)
    army.add_unit(leader)
    inner_circle.attached_leaders = [leader]
    leader.attached_to = inner_circle
    leader.can_be_attached_to = [inner_circle.name]
    inner_circle._invalidate_ability_cache()

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
        led_result = attack_profile._hit_target_with_tracking(
            inner_circle,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    assert led_result["hit"] is False
    assert any("Braziers of Judgement" in modifier for modifier in led_result.get("modifiers", []))
