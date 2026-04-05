import unittest
from types import SimpleNamespace


class TestLeaderWoundAllocation(unittest.TestCase):
    def test_bodyguards_take_wounds_first_then_leaders(self):
        from warhammer40k_ai.units.unit import Unit

        class _M:
            def __init__(self, alive=True):
                self.is_alive = alive
                self.wounds = 1
                self._base_wounds = 1
                self.objective_control = 1
                self.leadership = 7
                self.toughness = 4
                self.save = 3
                self.movement = 6

        class _U:
            def __init__(self, *, is_leader=False):
                self._ability_cache = {}
                self._datasheet = SimpleNamespace(id="X")
                self.can_be_attached_to = ["B1"] if is_leader else []
                self.attached_to = None
                self.attached_leaders = []
                self.models = [_M(True)]

            @property
            def is_leader(self):
                return len(self.can_be_attached_to) > 0

        bodyguard = _U(is_leader=False)
        leader = _U(is_leader=True)
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        # While bodyguard models remain, allocate to bodyguards only
        alloc1 = Unit.get_models_for_wound_allocation(bodyguard)
        self.assertEqual(len(alloc1), 1)
        self.assertIs(alloc1[0], bodyguard.models[0])

        # If bodyguard has no models left, allocate to leader models
        bodyguard.models = []
        alloc2 = Unit.get_models_for_wound_allocation(bodyguard)
        self.assertEqual(len(alloc2), 1)
        self.assertIs(alloc2[0], leader.models[0])


if __name__ == "__main__":
    unittest.main()


