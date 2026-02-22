from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        cost: int = 100,
        save: str = "4",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(save),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    cost: int = 100,
    save: str = "4",
) -> Unit:
    ds = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
        save=save,
    )
    unit = Unit(ds)
    unit.deployed = True
    return unit


def _make_profile(*, ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: not ranged,
        is_ranged=lambda: ranged,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _set_location(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def test_changehost_daemonic_illusions_grants_4_invuln_vs_ranged():
    army = Army("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
        save="6",
    )
    source = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    army.add_unit(target)
    army.add_unit(source)
    _set_location(target, 0.0, 0.0)
    _set_location(source, 4.0, 0.0)

    profile = _make_profile(ranged=True)
    save_res = profile._save_with_tracking(target.models[0], {}, ap=0, roll_value=1)
    assert int(save_res.get("final_save", 0) or 0) == 4


def test_changehost_daemonic_illusions_does_not_apply_to_melee():
    army = Army("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
        save="6",
    )
    source = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    army.add_unit(target)
    army.add_unit(source)
    _set_location(target, 0.0, 0.0)
    _set_location(source, 4.0, 0.0)

    profile = _make_profile(ranged=False)
    save_res = profile._save_with_tracking(target.models[0], {}, ap=0, roll_value=1)
    assert int(save_res.get("final_save", 0) or 0) == 6


def test_changehost_mortal_sorcery_grants_cabal_to_nearby_scintillating_legions_psyker():
    army = Army("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    ts_source = _make_unit(
        "Exalted Sorcerer",
        keywords=["THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
    )
    sl_psyker = _make_unit(
        "Kairos Fateweaver",
        keywords=["SCINTILLATING LEGIONS", "PSYKER"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    army.add_unit(ts_source)
    army.add_unit(sl_psyker)
    _set_location(ts_source, 0.0, 0.0)
    _set_location(sl_psyker, 4.0, 0.0)

    mgr = army.cabal_of_sorcerers
    assert mgr._unit_has_cabal(sl_psyker)

    _set_location(sl_psyker, 20.0, 0.0)
    assert not mgr._unit_has_cabal(sl_psyker)


def test_changehost_restriction_enforces_scintillating_legions_points_cap():
    army = Army("Thousand Sons", "Changehost of Deceit", points_limit=2000)
    army.faction_id = "TS"
    sl_1 = _make_unit(
        "Pink Horrors A",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=600,
    )
    sl_2 = _make_unit(
        "Pink Horrors B",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=600,
    )
    army.add_unit(sl_1)
    army.add_unit(sl_2)

    with pytest.raises(ArmyValidationError):
        army.validate_detachment_rules()


def test_changehost_restriction_disallows_scintillating_legions_warlord():
    army = Army("Thousand Sons", "Changehost of Deceit", points_limit=2000)
    army.faction_id = "TS"
    warlord = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=100,
    )
    warlord.is_warlord = True
    army.warlord = warlord
    army.add_unit(warlord)

    with pytest.raises(ArmyValidationError):
        army.validate_detachment_rules()


def test_changehost_restriction_valid_case_passes():
    army = Army("Thousand Sons", "Changehost of Deceit", points_limit=1000)
    army.faction_id = "TS"
    ts_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
        cost=200,
    )
    sl_unit = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=400,
    )
    ts_unit.is_warlord = True
    army.warlord = ts_unit
    army.add_unit(ts_unit)
    army.add_unit(sl_unit)

    army.validate_detachment_rules()
