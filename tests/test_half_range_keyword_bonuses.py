import unittest
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


class TestHalfRangeKeywordBonuses(unittest.TestCase):
    def _make_ranged_profile(self, *, keywords: str = "", name: str = "Test Weapon"):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
        parent = Wargear(data)
        return parent.profiles["default"]

    def test_half_range_sustained_hits_applies(self):
        ability = {
            "name": "Bladestorm",
            "description": (
                "Ranged weapons equipped by models in this unit have the [SUSTAINED HITS 1] ability "
                "while targeting an enemy unit within half range."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Dire Avengers", abilities=[ability])
        target = _make_unit("Target")
        profile = self._make_ranged_profile()
        attack_instance = {"below_half_distance": True, "distance_to_target": 6.0}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 1)

    def test_half_range_sustained_hits_not_applied_outside(self):
        ability = {
            "name": "Bladestorm",
            "description": (
                "Ranged weapons equipped by models in this unit have the [SUSTAINED HITS 1] ability "
                "while targeting an enemy unit within half range."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Dire Avengers", abilities=[ability])
        target = _make_unit("Target")
        profile = self._make_ranged_profile()
        attack_instance = {"below_half_distance": False, "distance_to_target": 13.0}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 0)

    def test_half_range_sustained_hits_value_respected(self):
        ability = {
            "name": "Focused Barrage",
            "description": (
                "Ranged weapons equipped by models in this unit have the [SUSTAINED HITS 2] ability "
                "while targeting an enemy unit within half range."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Testers", abilities=[ability])
        target = _make_unit("Target")
        profile = self._make_ranged_profile()
        attack_instance = {"below_half_distance": True, "distance_to_target": 6.0}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 2)

    def test_half_range_ignores_cover_applies(self):
        ability = {
            "name": "Close-Range Targeting",
            "description": (
                "Ranged weapons equipped by models in this unit have the [IGNORES COVER] ability "
                "while targeting an enemy unit within half range."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Shooters", abilities=[ability])
        target = _make_unit("Target")
        profile = self._make_ranged_profile()
        attack_instance = {"below_half_distance": True, "distance_to_target": 6.0}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)

        self.assertTrue(bool(attack_instance.get("ignores_cover")))

    def test_half_range_weapon_list_applies_only_to_named_weapons(self):
        ability = {
            "name": "Targeting Array",
            "description": (
                "This model's twin heavy rail cannon and seeker missiles have the [ANTI-TITANIC 3+] ability "
                "while targeting a unit within half range."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Shooter", abilities=[ability])
        target = _make_unit("Target", keywords=["TITANIC"])
        cannon_profile = self._make_ranged_profile(name="Twin Heavy Rail Cannon")
        missiles_profile = self._make_ranged_profile(name="Seeker Missiles")
        other_profile = self._make_ranged_profile(name="Burst Cannon")

        base_instance = {"below_half_distance": True, "distance_to_target": 6.0}
        cannon_instance = dict(base_instance)
        missiles_instance = dict(base_instance)
        other_instance = dict(base_instance)
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            cannon_profile._hit_target_with_tracking(target, attacker.models[0], cannon_instance)
            missiles_profile._hit_target_with_tracking(target, attacker.models[0], missiles_instance)
            other_profile._hit_target_with_tracking(target, attacker.models[0], other_instance)

        self.assertIn(("TITANIC", 3), tuple(cannon_instance.get("bonus_anti_specs") or ()))
        self.assertIn(("TITANIC", 3), tuple(missiles_instance.get("bonus_anti_specs") or ()))
        self.assertFalse(other_instance.get("bonus_anti_specs"))


if __name__ == "__main__":
    unittest.main()
