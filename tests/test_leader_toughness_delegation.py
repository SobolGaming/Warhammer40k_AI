import unittest
from types import SimpleNamespace


class TestLeaderToughnessDelegation(unittest.TestCase):
    def test_attached_leader_uses_bodyguard_toughness(self):
        from warhammer40k_ai.classes.unit import Unit

        class _M:
            def __init__(self, t):
                self.is_alive = True
                self.toughness = t
                self.wounds = 1
                self._base_wounds = 1
                self.objective_control = 1
                self.leadership = 7
                self.save = 3
                self.movement = 6

        class _U:
            def __init__(self, *, is_leader=False, t=4):
                self._datasheet = SimpleNamespace(id="X")
                self.can_be_attached_to = ["B1"] if is_leader else []
                self.attached_to = None
                self.attached_leaders = []
                self.models = [_M(t)]

            @property
            def is_leader(self):
                return len(self.can_be_attached_to) > 0

            @property
            def toughness(self):
                return self.models[0].toughness

        bodyguard = _U(is_leader=False, t=6)
        leader = _U(is_leader=True, t=4)
        leader.attached_to = bodyguard

        self.assertEqual(int(Unit.toughness.fget(leader)), 6)


if __name__ == "__main__":
    unittest.main()


