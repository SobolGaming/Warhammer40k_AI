import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        ds_id="",
        abilities=None,
        faction_name="Chaos Daemons",
        faction_keywords=None,
        attached_to=None,
        leadership="7",
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": leadership,
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
        self.attached_to = list(attached_to or [])


def _make_unit(name, *, ds_id="", abilities=None, attached_to=None, leadership="7"):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(
        name,
        ds_id=ds_id,
        abilities=abilities,
        attached_to=attached_to,
        leadership=leadership,
    )
    return Unit(datasheet)


class TestBearerUnitCommonAbilities(unittest.TestCase):
    def test_bearer_unit_charge_bonus_applies(self):
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "Instrument of Chaos",
            "description": "Add 1 to Charge rolls made for the bearer's unit.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Instrument of Chaos")
        unit._refresh_bearer_unit_common_modifiers()

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(unit, 7), 8)

    def test_bearer_unit_leadership_set_applies(self):
        ability = {
            "name": "Daemonic Icon",
            "description": "Models in the bearer's unit have a Leadership characteristic of 6+.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Daemon", abilities=[ability], leadership="7")
        unit.models[0].optional_wargear.append("Daemonic Icon")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit.leadership, 6)

    def test_attached_leader_bearer_unit_leadership_applies_to_bodyguard(self):
        from warhammer40k_ai.classes.army import Army

        ability = {
            "name": "Daemonic Icon",
            "description": "Models in the bearer's unit have a Leadership characteristic of 6+.",
            "type": "Wargear",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG1", abilities=[], leadership="5")
        leader = _make_unit("Leader", ds_id="LD1", abilities=[ability], attached_to=["BG1"], leadership="7")
        leader.models[0].optional_wargear.append("Daemonic Icon")

        army = Army("Chaos Daemons", "Detachment")
        army.faction_id = "CD"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        self.assertEqual(bodyguard.leadership, 6)


if __name__ == "__main__":
    unittest.main()
