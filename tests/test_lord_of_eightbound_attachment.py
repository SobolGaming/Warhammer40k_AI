import unittest


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        attached_to=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "5",
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(*, name, datasheet_id, keywords=None, faction_keywords=None, abilities=None, attached_to=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class TestLordOfTheEightboundAttachment(unittest.TestCase):
    def test_attached_possessed_grants_deep_strike_and_scouts(self):
        ability = {
            "name": "LORD OF THE EIGHTBOUND",
            "description": (
                'If this model is attached to a WORLD EATERS POSSESSED unit during the Declare Battle Formations step, '
                'until the end of the battle, this model has the Deep Strike and Scouts 6" abilities.'
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit(
            name="Slaughterbound",
            datasheet_id="leader1",
            abilities=[ability],
            attached_to=["bodyguard_possessed", "bodyguard_plain"],
        )
        bodyguard_possessed = _make_unit(
            name="Eightbound",
            datasheet_id="bodyguard_possessed",
            keywords=["POSSESSED"],
            faction_keywords=["WORLD EATERS"],
        )
        bodyguard_plain = _make_unit(
            name="Jakhals",
            datasheet_id="bodyguard_plain",
            faction_keywords=["WORLD EATERS"],
        )
        shared_army = object()
        leader.set_parent_army(shared_army)
        bodyguard_possessed.set_parent_army(shared_army)
        bodyguard_plain.set_parent_army(shared_army)

        self.assertFalse(leader.has_deep_strike())
        self.assertEqual(leader.has_scout(), (False, 0.0))

        leader.attach_to_unit(bodyguard_plain)
        self.assertFalse(leader.has_deep_strike())
        self.assertEqual(leader.has_scout(), (False, 0.0))
        leader.detach_from_unit()

        leader.attach_to_unit(bodyguard_possessed)
        self.assertTrue(leader.has_deep_strike())
        self.assertEqual(leader.has_scout(), (True, 6.0))
        self.assertFalse(bodyguard_possessed.has_deep_strike())
        self.assertEqual(bodyguard_possessed.has_scout(), (False, 0.0))

        leader.detach_from_unit()
        self.assertTrue(leader.has_deep_strike())
        self.assertEqual(leader.has_scout(), (True, 6.0))


if __name__ == "__main__":
    unittest.main()
