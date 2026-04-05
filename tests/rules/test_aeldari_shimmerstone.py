import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class TestAeldariShimmerstone(unittest.TestCase):
    def _make_ranged_profile(self):
        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
        }
        parent = Wargear({"name": "Test Rifle", "type": "Ranged", **data})
        return parent.profiles["default"]

    def _make_unit(self, army, *, name, keywords):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = list(keywords or [])
        unit.faction_keywords = ["Aeldari"]
        unit.models = [SimpleNamespace(is_alive=True, toughness=4, save=3, inv_save=None)]
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.possible_abilities = []
        return unit

    def test_shimmerstone_applies_wound_penalty(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Aeldari", detachment_type="Aspect Host")
        army.faction_id = "AE"

        target = self._make_unit(army, name="Dire Avengers", keywords=["Aspect Warriors"])
        leader = self._make_unit(army, name="Autarch", keywords=["Character"])
        leader.special_rules = {"enhancement_shimmerstone": True}
        leader.attached_to = target
        target.attached_leaders = [leader]

        attacker_unit = self._make_unit(army, name="Attacker", keywords=["Infantry"])
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        profile = self._make_ranged_profile()
        attack_instance = {}
        result = profile._wound_target_with_tracking(
            target,
            attacker_model,
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertIn("-1 to wound from Shimmerstone", result.get("modifiers", []))


if __name__ == "__main__":
    unittest.main()
