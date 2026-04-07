import pytest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.modifiers import compute_save_roll_modifier


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        save: str = "4",
        inv_sv: str = "7",
        inv_sv_descr: str = "",
    ):
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(save),
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(inv_sv),
                "inv_sv_descr": str(inv_sv_descr),
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(name: str, *, keywords=None, faction_keywords=None, save: str = "4") -> Unit:
    ds = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        save=save,
    )
    unit = Unit(ds)
    unit.deployed = True
    return unit


def make_weapon_profile(*, damage: str = "1") -> WargearProfile:
    return WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
    )


def test_all_is_dust_applies_to_rubricae_armor_saves(monkeypatch):
    import warhammer40k_ai.units.wargear as wargear_mod

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)

    army = Army.with_detachment("Thousand Sons", "Rubricae Phalanx")
    army.faction_id = "TS"

    unit = create_unit("Rubric Marines", keywords=["RUBRICAE", "THOUSAND SONS"])
    army.add_unit(unit)

    weapon = make_weapon_profile(damage="1")
    res = weapon._save_with_tracking(unit.models[0], {"mortal_wound": False}, ap=0)

    assert res["saved"] is True
    assert any("All is Dust" in eff for eff in (res.get("special_effects") or []))


def test_all_is_dust_requires_rubricae_and_detachment():
    army = Army.with_detachment("Thousand Sons", "Rubricae Phalanx")
    army.faction_id = "TS"

    non_rubricae = create_unit("Sorcerer", keywords=["THOUSAND SONS", "CHARACTER"])
    army.add_unit(non_rubricae)

    weapon = SimpleNamespace(damage=1)
    mod, effects = compute_save_roll_modifier(
        non_rubricae.models[0],
        attack_instance={},
        ap=0,
        save_type="armor",
        weapon_profile=weapon,
    )
    assert mod == 0
    assert not any("All is Dust" in eff for eff in (effects or []))

    other_army = Army.with_detachment("Thousand Sons", "Other Detachment")
    other_army.faction_id = "TS"

    rubricae = create_unit("Rubric Marines", keywords=["RUBRICAE", "THOUSAND SONS"])
    other_army.add_unit(rubricae)

    mod2, effects2 = compute_save_roll_modifier(
        rubricae.models[0],
        attack_instance={},
        ap=0,
        save_type="armor",
        weapon_profile=weapon,
    )
    assert mod2 == 0
    assert not any("All is Dust" in eff for eff in (effects2 or []))

    mod3, _effects3 = compute_save_roll_modifier(
        rubricae.models[0],
        attack_instance={},
        ap=0,
        save_type="invulnerable",
        weapon_profile=weapon,
    )
    assert mod3 == 0
