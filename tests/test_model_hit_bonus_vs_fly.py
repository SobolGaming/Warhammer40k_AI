import unittest
from types import SimpleNamespace
from unittest.mock import patch


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


def _make_unit(name, *, abilities=None, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, keywords=keywords)
    return Unit(datasheet)


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestModelHitBonusVsFly(unittest.TestCase):
    def test_hit_bonus_vs_fly_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Skyhunter",
            "description": (
                "Each time this model makes an attack that targets a unit that can FLY, "
                "add 1 to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Attacker", abilities=[ability])
        target = _make_unit("Target", keywords=["Fly"])

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            result = profile._hit_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertTrue(result["hit"])
        self.assertEqual(int(result.get("final_needed", 0)), 2)
        self.assertIn("+1 to hit from Skyhunter (vs FLY targets)", result.get("modifiers", []))

    def test_no_bonus_vs_non_fly_target(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Skyhunter",
            "description": (
                "Each time this model makes an attack that targets a unit that can FLY, "
                "add 1 to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Attacker", abilities=[ability])
        target = _make_unit("Target")

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            result = profile._hit_target_with_tracking(
                target,
                attacker.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertFalse(result["hit"])
        self.assertEqual(int(result.get("final_needed", 0)), 3)
        self.assertNotIn("+1 to hit from Skyhunter (vs FLY targets)", result.get("modifiers", []))


if __name__ == "__main__":
    unittest.main()
