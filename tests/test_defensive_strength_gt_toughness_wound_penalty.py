import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, toughness=4, wounds=3):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
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


def _make_unit(name, *, abilities=None, toughness=4, wounds=3):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, toughness=toughness, wounds=wounds)
    return Unit(datasheet)


class TestDefensiveStrengthGtToughnessWoundPenalty(unittest.TestCase):
    def test_ranged_targets_strength_gt_toughness_penalty(self):
        from warhammer40k_ai.units.wargear import Wargear

        ability = {
            "name": "Reactive Plating",
            "description": (
                "Each time a ranged attack targets this model, if the Strength characteristic of that attack "
                "is greater than the Toughness characteristic of this model, subtract 1 from the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        target = _make_unit("Target", abilities=[ability], toughness=4)
        attacker = _make_unit("Attacker", toughness=4)

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = attacker.models[0]

        wound = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Reactive Plating" in m for m in wound.get("modifiers", [])))

        weapon_equal = Wargear(
            {
                "name": "Test Gun Equal",
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
        profile_equal = weapon_equal.profiles["default"]
        wound_equal = profile_equal._wound_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Reactive Plating" in m for m in wound_equal.get("modifiers", [])))

        melee_weapon = Wargear(
            {
                "name": "Test Blade",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "6",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        melee_profile = melee_weapon.profiles["default"]
        melee_wound = melee_profile._wound_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Reactive Plating" in m for m in melee_wound.get("modifiers", [])))


if __name__ == "__main__":
    unittest.main()
