import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
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
        self.transport = ""


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import Wargear

    wargear = Wargear(
        {
            "name": "Test Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return next(iter(wargear.profiles.values()))


class TestLeadingShootChargeEligibilityAdvanceFallBack(unittest.TestCase):
    def test_attached_leader_grants_shoot_and_charge_after_advance_and_fall_back(self):
        ability = {
            "name": "Ride and Ruin",
            "description": (
                "While this model is leading a unit, that unit is eligible to shoot and declare a charge in a turn "
                "in which it Advanced or Fell Back."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]
        profile = _make_ranged_profile()

        self.assertTrue(bodyguard.has_advance_and_shoot())
        self.assertTrue(bodyguard.can_shoot_after_advance(profile))
        self.assertTrue(bodyguard.has_fell_back_and_shoot())
        self.assertTrue(bodyguard.can_shoot_after_fall_back(profile))
        self.assertTrue(bodyguard.has_advance_and_charge())
        self.assertTrue(bodyguard.can_charge_after_advance())
        self.assertTrue(bodyguard.can_charge_after_fall_back())

    def test_leading_clause_is_inactive_when_not_attached(self):
        ability = {
            "name": "Ride and Ruin",
            "description": (
                "While this model is leading a unit, that unit is eligible to shoot and declare a charge in a turn "
                "in which it Advanced or Fell Back."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        leader.can_be_attached_to = ["Bodyguard"]
        profile = _make_ranged_profile()

        self.assertFalse(leader.has_advance_and_shoot())
        self.assertFalse(leader.can_shoot_after_advance(profile))
        self.assertFalse(leader.has_fell_back_and_shoot())
        self.assertFalse(leader.can_shoot_after_fall_back(profile))
        self.assertFalse(leader.has_advance_and_charge())
        self.assertFalse(leader.can_charge_after_advance())
        self.assertFalse(leader.can_charge_after_fall_back())


if __name__ == "__main__":
    unittest.main()
