import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, abilities=None, cost=100):
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["TAU EMPIRE"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None) -> Unit:
    datasheet = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    return Unit(datasheet)


def test_tau_independent_power_blocks_farsight_with_ethereal_units():
    army = Army.with_detachment("T'au Empire", "Kauyon", points_limit=2000)
    farsight = make_unit(
        "Commander Farsight",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[{
            "name": "INDEPENDENT POWER",
            "description": (
                "If your army includes COMMANDER FARSIGHT, it cannot include any Ethereal units. "
                "If your army includes any ETHEREAL units, it cannot include COMMANDER FARSIGHT."
            ),
            "type": "Special",
            "parameter": "",
        }],
    )
    ethereal = make_unit("Ethereal", keywords=["CHARACTER", "INFANTRY", "ETHEREAL"])
    army.add_unit(farsight)
    army.add_unit(ethereal)

    with pytest.raises(ArmyValidationError, match="INDEPENDENT POWER"):
        army.validate_tau_independent_power()


def test_tau_independent_power_allows_farsight_without_ethereals():
    army = Army.with_detachment("T'au Empire", "Kauyon", points_limit=2000)
    farsight = make_unit("Commander Farsight", keywords=["CHARACTER", "INFANTRY"])
    strike_team = make_unit("Strike Team", keywords=["INFANTRY", "BATTLELINE"])
    army.add_unit(farsight)
    army.add_unit(strike_team)

    army.validate_tau_independent_power()


def test_tau_independent_power_allows_ethereals_without_farsight():
    army = Army.with_detachment("T'au Empire", "Kauyon", points_limit=2000)
    ethereal = make_unit("Ethereal", keywords=["CHARACTER", "INFANTRY", "ETHEREAL"])
    strike_team = make_unit("Strike Team", keywords=["INFANTRY", "BATTLELINE"])
    army.add_unit(ethereal)
    army.add_unit(strike_team)

    army.validate_tau_independent_power()

