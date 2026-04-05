import unittest
from unittest.mock import patch
from types import SimpleNamespace


class _DummyUnit:
    def __init__(self, charged: bool):
        self.round_state = SimpleNamespace(charged_this_round=charged)


class _DummyModel:
    def __init__(self, charged: bool):
        self.name = "Attacker"
        self.parent_unit = _DummyUnit(charged=charged)


class _DummyTarget:
    def __init__(self, toughness: int = 5):
        self.toughness = toughness
        self.models = [SimpleNamespace(is_alive=True)]

    def has_keyword(self, k: str) -> bool:
        return False


class TestLanceTwinLinked(unittest.TestCase):
    def _make_profile(self, keywords: str, strength: int = 4):
        from warhammer40k_ai.units.wargear import WargearProfile, Wargear

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
        parent = Wargear({"name": "Test Weapon", "type": "Melee", **data})
        # parent.profiles["default"] is a WargearProfile already; use it.
        return parent.profiles["default"]

    def test_lance_adds_plus_one_to_wound_when_charged(self):
        # S4 vs T5 normally wounds on 5+. With Lance after charge, wounds on 4+.
        profile = self._make_profile("lance", strength=4)
        attacker = _DummyModel(charged=True)
        target = _DummyTarget(toughness=5)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
        self.assertTrue(res["wound"])
        self.assertIn("+1 to wound from Lance (charged)", res.get("modifiers", []))

    def test_twin_linked_rerolls_failed_wound(self):
        # S4 vs T4 wounds on 4+. Roll 1 (fail) -> reroll 4 (success).
        profile = self._make_profile("twin-linked", strength=4)
        attacker = _DummyModel(charged=False)
        target = _DummyTarget(toughness=4)

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
        self.assertTrue(res["wound"])
        self.assertEqual(res.get("reroll"), 4)
        self.assertIn("Twin-linked (re-roll failed wound)", res.get("special_effects", []))


if __name__ == "__main__":
    unittest.main()

