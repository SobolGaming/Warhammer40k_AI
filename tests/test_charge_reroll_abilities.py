import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        ds_id="",
        abilities=None,
        attached_to=None,
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "2",
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])


def _make_unit(name, *, ds_id="", abilities=None, attached_to=None):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(
        name,
        ds_id=ds_id,
        abilities=abilities,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class TestChargeRerollAbilities(unittest.TestCase):
    def test_unit_reroll_charge_rolls(self):
        ability = {
            "name": "Relentless Combatants",
            "description": "You can re-roll Charge rolls made for this unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Lychguard", abilities=[ability])
        self.assertTrue(unit.can_reroll_charge_roll())

    def test_leading_reroll_charge_rolls_requires_attachment(self):
        from warhammer40k_ai.classes.unit import Unit

        ability = {
            "name": "Zealous Path",
            "description": "While this model is leading a unit, you can re-roll Charge rolls made for that unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG1")
        leader = _make_unit("Chaplain", ds_id="LD1", abilities=[ability], attached_to=["BG1"])

        class _Army:
            def __init__(self, units):
                self.units = list(units)
                self.player = None
                self.faction_id = "GK"

            def on_battle_round_start(self, *_a, **_k):
                return None

        army = _Army([bodyguard, leader])
        bodyguard.set_parent_army(army)
        leader.set_parent_army(army)

        self.assertFalse(bodyguard.can_reroll_charge_roll())

        leader.attach_to_unit(bodyguard)

        self.assertTrue(bodyguard.can_reroll_charge_roll())
        self.assertTrue(leader.is_attached_leader)


if __name__ == "__main__":
    unittest.main()
