import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, cost=100):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, faction_keywords=None, cost=100) -> Unit:
    datasheet = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, cost=cost)
    return Unit(datasheet)


def setup_reapers_wager_army(points_limit=2000) -> Army:
    army = Army.with_detachment("Drukhari", "Reaper's Wager", points_limit=points_limit)
    army.faction_id = "DRU"
    base = make_unit("Kabalites", faction_keywords=["DRUKHARI"])
    army.add_unit(base)
    return army


def test_reapers_wager_allows_harlequins_under_cap():
    army = setup_reapers_wager_army(points_limit=2000)
    harl = make_unit("Troupe", faction_keywords=["HARLEQUINS"], cost=900)
    army.add_unit(harl)
    army.validate_allies()


def test_reapers_wager_harlequins_points_cap_enforced():
    army = setup_reapers_wager_army(points_limit=2000)
    harl_a = make_unit("Troupe A", faction_keywords=["HARLEQUINS"], cost=600)
    harl_b = make_unit("Troupe B", faction_keywords=["HARLEQUINS"], cost=500)
    army.add_unit(harl_a)
    army.add_unit(harl_b)
    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_reapers_wager_harlequins_cannot_be_warlord():
    army = setup_reapers_wager_army(points_limit=2000)
    harl = make_unit("Troupe", faction_keywords=["HARLEQUINS"], cost=200)
    harl.is_warlord = True
    army.add_unit(harl)
    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_reapers_wager_disables_corsairs_and_travelling_players_anhrathe_allies():
    army = setup_reapers_wager_army(points_limit=2000)
    corsair = make_unit("Corsair Voidreavers", faction_keywords=["ANHRATHE"], cost=200)
    army.add_unit(corsair)
    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_reapers_wager_does_not_apply_corsairs_enhancement_ban():
    army = setup_reapers_wager_army(points_limit=2000)
    harl = make_unit("Troupe Master", faction_keywords=["HARLEQUINS"], cost=200)
    harl.enhancement = Enhancement(
        id="enh",
        name="Test Enhancement",
        faction_id="DRU",
        detachment="Reaper's Wager",
        points=10,
    )
    army.add_unit(harl)
    army.validate_allies()
