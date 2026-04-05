import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestMartialKatahCombatInjection(unittest.TestCase):
    def _make_melee_profile(self, keywords: str = ""):
        from warhammer40k_ai.units.wargear import Wargear
        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
        parent = Wargear({"name": "Test Weapon", "type": "Melee", **data})
        return parent.profiles["default"]

    def _mk_attacker(self, *, choice: str):
        class _Unit:
            def __init__(self, choice_key: str):
                self.special_rules = {"martial_katah_choice": choice_key}

            def get_attached_unit_root(self):
                return self

            def attached_unit_has_martial_katah(self):
                return True

        unit = _Unit(choice)
        attacker = SimpleNamespace(name="Attacker", parent_unit=unit)
        return attacker

    def test_dacatarai_grants_sustained_hits_on_melee_crit(self):
        profile = self._make_melee_profile("")
        attacker = self._mk_attacker(choice="DACATARAI")
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

    def test_rendax_grants_lethal_hits_on_melee_crit(self):
        profile = self._make_melee_profile("")
        attacker = self._mk_attacker(choice="RENDAX")
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("lethal_hit", False))


if __name__ == "__main__":
    unittest.main()
