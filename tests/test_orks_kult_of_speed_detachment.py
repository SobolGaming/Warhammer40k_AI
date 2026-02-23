from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "2",
                "base_size": "75x42mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Dakkagun",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "3",
        "BS_WS": "5+",
        "S": "5",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_army_with_unit(*, detachment: str, unit: Unit) -> Army:
    army = Army("Orks", detachment)
    army.faction_id = "ORK"
    army.add_unit(unit)
    Player("Ork Player", control=PlayerControl.LOCAL, army=army)
    return army


def test_adrenaline_junkies_grants_speed_freeks_shoot_and_charge_after_advance_or_fall_back():
    unit = _create_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    _build_army_with_unit(detachment="Kult of Speed", unit=unit)
    profile = _make_ranged_profile()

    assert unit.can_shoot_after_advance(profile) is True
    assert unit.can_shoot_after_fall_back(profile) is True
    assert unit.can_charge_after_advance() is True
    assert unit.can_charge_after_fall_back() is True


def test_adrenaline_junkies_does_not_apply_outside_kult_of_speed():
    unit = _create_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    _build_army_with_unit(detachment="War Horde", unit=unit)
    profile = _make_ranged_profile()

    assert unit.can_shoot_after_advance(profile) is False
    assert unit.can_shoot_after_fall_back(profile) is False
    assert unit.can_charge_after_advance() is False
    assert unit.can_charge_after_fall_back() is False


def test_adrenaline_junkies_does_not_apply_to_non_speed_freeks_units():
    unit = _create_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
    )
    _build_army_with_unit(detachment="Kult of Speed", unit=unit)
    profile = _make_ranged_profile()

    assert unit.can_shoot_after_advance(profile) is False
    assert unit.can_shoot_after_fall_back(profile) is False
    assert unit.can_charge_after_advance() is False
    assert unit.can_charge_after_fall_back() is False
