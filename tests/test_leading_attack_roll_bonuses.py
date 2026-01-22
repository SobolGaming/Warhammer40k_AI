import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, model_count=1, wounds=2):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
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


def _make_unit(name, *, abilities=None, model_count=1, wounds=2):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, model_count=model_count, wounds=wounds)
    return Unit(datasheet)


class TestLeadingAttackRollBonuses(unittest.TestCase):
    def _attach(self, leader, bodyguard):
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = [bodyguard.name]

    def test_leading_hit_bonus_applies(self):
        ability = {
            "name": "Relentless Assault",
            "description": (
                "While this model is leading a unit, each time a model in that unit makes an attack, "
                "add 1 to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        self._attach(leader, bodyguard)

        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertEqual(int(mods.get("hit", 0)), 1)

    def test_leading_wound_bonus_applies(self):
        ability = {
            "name": "Savage Blows",
            "description": (
                "While this model is leading a unit, each time a model in that unit makes an attack, "
                "add 1 to the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        self._attach(leader, bodyguard)

        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertEqual(int(mods.get("wound", 0)), 1)

    def test_leading_battleshocked_wound_bonus(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        ability = {
            "name": "Merciless Execution",
            "description": (
                "While this model is leading a unit, each time a model in that unit makes an attack, "
                "add 1 to the Hit roll. If the target is battle-shocked, add 1 to the Wound roll as well."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        target = _make_unit("Enemy")
        self._attach(leader, bodyguard)

        mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=target)
        self.assertEqual(int(mods.get("hit", 0)), 1)
        self.assertEqual(int(mods.get("wound", 0)), 0)

        target.status_effects.append(BattleShockEffect())
        mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=target)
        self.assertEqual(int(mods.get("hit", 0)), 1)
        self.assertEqual(int(mods.get("wound", 0)), 1)

    def test_leading_below_strength_bonus(self):
        ability = {
            "name": "Blooded Veterans",
            "description": (
                "While this model is leading a unit, each time a model in that unit makes an attack, add 1 "
                "to the Hit roll if that unit is below its Starting Strength, and add 1 to the Wound roll "
                "as well if that unit is below Half-strength."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard", model_count=4)
        self._attach(leader, bodyguard)

        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertEqual(int(mods.get("hit", 0)), 0)
        self.assertEqual(int(mods.get("wound", 0)), 0)

        bodyguard.remove_model(bodyguard.models[0])
        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertEqual(int(mods.get("hit", 0)), 1)
        self.assertEqual(int(mods.get("wound", 0)), 0)

        while len(bodyguard.models) > 1:
            bodyguard.remove_model(bodyguard.models[0])
        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertEqual(int(mods.get("hit", 0)), 1)
        self.assertEqual(int(mods.get("wound", 0)), 1)

    def test_model_self_strength_bonus(self):
        ability = {
            "name": "Glutton for Punishment",
            "description": (
                "Each time this model makes an attack, if it is below its Starting Strength, add 1 to the Hit roll. "
                "If this model is also Below Half-strength, add 1 to the Wound roll as well."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Glutton", abilities=[ability], model_count=1, wounds=5)
        model = unit.models[0]

        mods = unit.model_attack_roll_modifiers_vs_weakened_target(model, attack_type="melee", target=None)
        self.assertEqual(int(mods.get("hit", 0)), 0)
        self.assertEqual(int(mods.get("wound", 0)), 0)

        model.wounds = 4
        mods = unit.model_attack_roll_modifiers_vs_weakened_target(model, attack_type="melee", target=None)
        self.assertEqual(int(mods.get("hit", 0)), 1)
        self.assertEqual(int(mods.get("wound", 0)), 0)

        model.wounds = 2
        mods = unit.model_attack_roll_modifiers_vs_weakened_target(model, attack_type="melee", target=None)
        self.assertEqual(int(mods.get("hit", 0)), 1)
        self.assertEqual(int(mods.get("wound", 0)), 1)


if __name__ == "__main__":
    unittest.main()
