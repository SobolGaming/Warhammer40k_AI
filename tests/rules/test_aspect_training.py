import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        datasheet_id,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        base_size="32mm",
        attached_to=None,
        attached_to_names=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
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
        self.attached_to_names = list(attached_to_names or [])


def _make_unit(
    name,
    datasheet_id,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
    attached_to=None,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class TestAspectTraining(unittest.TestCase):
    def test_aspect_training_banshees_only_grants_fight_first(self):
        ability = [
            {
                "name": "ASPECT TRAINING",
                "description": (
                    "<ul><li>While this model is leading a Howling Banshees unit, it has the Fights First ability.</li>"
                    "<li>While this model is leading a Striking Scorpions unit, it has the Infiltrators, Scouts 7\" "
                    "and Stealth abilities.</li></ul>"
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        banshees = _make_unit(
            "Howling Banshees",
            "B1",
            keywords=["Howling Banshees"],
        )
        leader = _make_unit(
            "Autarch",
            "L1",
            abilities=ability,
            attached_to=["B1"],
        )
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Test", detachment_type="Test")
        army.add_unit(banshees)
        army.add_unit(leader)

        leader.attach_to_unit(banshees)

        self.assertTrue(leader.has_fight_first())
        self.assertFalse(leader.has_infiltrate())
        self.assertEqual(leader.has_scout(), (False, 0.0))
        self.assertFalse(leader.has_stealth())

    def test_aspect_training_scorpions_grants_infiltrators_scouts_and_stealth(self):
        ability = [
            {
                "name": "ASPECT TRAINING",
                "description": (
                    "<ul><li>While this model is leading a Howling Banshees unit, it has the Fights First ability.</li>"
                    "<li>While this model is leading a Striking Scorpions unit, it has the Infiltrators, Scouts 7\" "
                    "and Stealth abilities.</li></ul>"
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        scorpions = _make_unit(
            "Striking Scorpions",
            "S1",
            abilities=[
                {"name": "Infiltrators", "description": "", "type": "Datasheet", "parameter": ""},
                {"name": "Scouts 7\"", "description": "", "type": "Datasheet", "parameter": ""},
                {"name": "Stealth", "description": "", "type": "Datasheet", "parameter": ""},
            ],
            keywords=["Striking Scorpions"],
        )
        leader = _make_unit(
            "Autarch",
            "L2",
            abilities=ability,
            attached_to=["S1"],
        )
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Test", detachment_type="Test")
        army.add_unit(scorpions)
        army.add_unit(leader)

        leader.attach_to_unit(scorpions)

        self.assertFalse(leader.has_fight_first())
        self.assertTrue(leader.has_infiltrate())
        self.assertEqual(leader.has_scout(), (True, 7.0))
        self.assertTrue(leader.has_stealth())
        self.assertEqual(scorpions.has_scout(), (True, 7.0))
