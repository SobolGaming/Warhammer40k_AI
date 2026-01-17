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


def make_unit(name: str, *, keywords=None, faction_keywords=None, cost=100, battleline=False) -> Unit:
    kw = list(keywords or [])
    if battleline and "Battleline" not in kw:
        kw.append("Battleline")
    datasheet = MockDatasheet(name, keywords=kw, faction_keywords=faction_keywords, cost=cost)
    return Unit(datasheet)


def setup_csm_army(points_limit=2000) -> Army:
    army = Army("Chaos Space Marines", "Detachment", points_limit=points_limit)
    army.faction_id = "CSM"
    base = make_unit("CSM Unit", faction_keywords=["HERETIC ASTARTES"])
    army.add_unit(base)
    return army


def test_daemonic_pact_allows_under_cap_and_ratio():
    army = setup_csm_army()
    daemon_bl = make_unit("Daemon BL", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=150)
    daemon_nb = make_unit("Daemon NB", keywords=["LEGIONES DAEMONICA", "KHORNE"], cost=150)
    army.add_unit(daemon_bl)
    army.add_unit(daemon_nb)

    army.validate_allies()


def test_daemonic_pact_points_cap_enforced():
    army = setup_csm_army()
    daemon1 = make_unit("Daemon 1", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=300)
    daemon2 = make_unit("Daemon 2", keywords=["LEGIONES DAEMONICA", "KHORNE"], cost=250)
    army.add_unit(daemon1)
    army.add_unit(daemon2)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_daemonic_pact_warlord_forbidden():
    army = setup_csm_army()
    daemon = make_unit("Daemon", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=100)
    daemon.is_warlord = True
    army.add_unit(daemon)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_daemonic_pact_enhancement_forbidden():
    army = setup_csm_army()
    daemon = make_unit("Daemon", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=100)
    daemon.enhancement = Enhancement(
        id="enh",
        name="Test Enhancement",
        faction_id="CSM",
        detachment="Detachment",
        points=10,
    )
    army.add_unit(daemon)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_daemonic_pact_non_battleline_ratio():
    army = setup_csm_army()
    daemon_bl = make_unit("Daemon BL", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=100)
    daemon_nb1 = make_unit("Daemon NB1", keywords=["LEGIONES DAEMONICA", "KHORNE"], cost=100)
    daemon_nb2 = make_unit("Daemon NB2", keywords=["LEGIONES DAEMONICA", "KHORNE"], cost=100)
    army.add_unit(daemon_bl)
    army.add_unit(daemon_nb1)
    army.add_unit(daemon_nb2)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_daemonic_pact_requires_base_keyword():
    army = setup_csm_army()
    outsider = make_unit("Outsider", faction_keywords=["IMPERIUM"])
    daemon = make_unit("Daemon", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=100)
    army.add_unit(outsider)
    army.add_unit(daemon)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_daemonic_pact_rejects_other_factions():
    army = Army("Other", "Detachment", points_limit=2000)
    army.faction_id = "SM"
    base = make_unit("Base", faction_keywords=["ADEPTUS ASTARTES"])
    daemon = make_unit("Daemon", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=100)
    army.add_unit(base)
    army.add_unit(daemon)

    with pytest.raises(ArmyValidationError):
        army.validate_allies()


def test_daemonic_pact_disables_shadow_of_chaos():
    from warhammer40k_ai.rules.shadow_of_chaos import ShadowOfChaosManager

    army = setup_csm_army()
    daemon = make_unit("Daemon", keywords=["LEGIONES DAEMONICA", "KHORNE"], battleline=True, cost=100)
    army.add_unit(daemon)

    mgr = ShadowOfChaosManager(army)
    assert mgr.army_has_shadow() is False
