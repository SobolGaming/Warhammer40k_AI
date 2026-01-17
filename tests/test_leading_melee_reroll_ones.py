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


class TestLeadingMeleeRerollOnes(unittest.TestCase):
    def test_leading_melee_reroll_hit_and_wound_ones(self):
        ability = {
            "name": "Legendary Killer",
            "description": (
                "While this model is leading a unit, each time a model in that unit makes a melee attack, "
                "re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")

        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertTrue(mods.get("reroll_hit_ones"))
        self.assertTrue(mods.get("reroll_wound_ones"))
        self.assertTrue(any("Legendary Killer" in r for r in (mods.get("reroll_hit_reasons") or ())))
        self.assertTrue(any("Legendary Killer" in r for r in (mods.get("reroll_wound_reasons") or ())))


if __name__ == "__main__":
    unittest.main()
