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


class TestAttachedBattlelineInfiltratorsScouts(unittest.TestCase):
    def test_attached_to_ec_battleline_grants_infiltrators_and_scouts(self):
        from warhammer40k_ai.roster.army import Army

        ability = [
            {
                "name": "Perfect Accompaniment",
                "description": (
                    "If this model is attached to an Emperor's Children Battleline unit during the Declare Battle "
                    "Formations step, this model has the Infiltrators and Scouts 6\" abilities."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        bodyguard = _make_unit(
            "Noise Marines",
            "BG1",
            keywords=["Battleline"],
            faction_keywords=["Emperor's Children"],
        )
        leader = _make_unit(
            "Lord",
            "L1",
            abilities=ability,
            attached_to=["BG1"],
        )
        army = Army.with_detachment("Emperor's Children", detachment_type="Test")
        army.add_unit(bodyguard)
        army.add_unit(leader)

        self.assertFalse(leader.has_infiltrate())
        self.assertEqual(leader.has_scout(), (False, 0.0))

        leader.attach_to_unit(bodyguard)
        self.assertTrue(leader.has_infiltrate())
        self.assertEqual(leader.has_scout(), (True, 6.0))
        self.assertEqual(bodyguard.has_scout(), (False, 0.0))
