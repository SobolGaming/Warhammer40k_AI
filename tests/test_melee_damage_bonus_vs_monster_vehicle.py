import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name, *, abilities=None, keywords=None):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, keywords=keywords)
    return Unit(datasheet)


class TestMeleeDamageBonusVsMonsterVehicle(unittest.TestCase):
    def _make_melee_profile(self, *, damage: str = "1"):
        from warhammer40k_ai.classes.wargear import Wargear

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": damage,
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        return parent.profiles["default"]

    def test_melee_damage_bonus_applies_vs_monster(self):
        ability = {
            "name": "Rend and Tear",
            "description": (
                "Each time a model in this unit makes a melee attack that targets a MONSTER or VEHICLE unit, "
                "until the end of the phase, improve the Damage characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Attacker", abilities=[ability])
        target = _make_unit("Target", keywords=["Monster"])

        profile = self._make_melee_profile(damage="1")
        attacker_model = attacker.models[0]
        target_model = target.models[0]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 2)

    def test_melee_damage_bonus_does_not_apply_without_keyword(self):
        ability = {
            "name": "Rend and Tear",
            "description": (
                "Each time a model in this unit makes a melee attack that targets a MONSTER or VEHICLE unit, "
                "until the end of the phase, improve the Damage characteristic of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Attacker", abilities=[ability])
        target = _make_unit("Target", keywords=["Infantry"])

        profile = self._make_melee_profile(damage="1")
        attacker_model = attacker.models[0]
        target_model = target.models[0]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 1)


if __name__ == "__main__":
    unittest.main()
