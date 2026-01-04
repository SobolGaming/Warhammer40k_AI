import unittest
from types import SimpleNamespace

from warhammer40k_ai.classes.unit import Unit


class TestThrillSeekers(unittest.TestCase):
    def _make_unit(self, *, advanced=False, fell_back=False, engaged_ids=None):
        unit = Unit.__new__(Unit)
        unit._id = "unit-a"
        unit.possible_abilities = ["Thrill Seekers"]
        unit.round_state = SimpleNamespace(
            advanced_this_round=advanced,
            fell_back_this_round=fell_back,
            engaged_enemies_at_turn_start=set(engaged_ids or []),
        )
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.keywords = []
        unit.faction_keywords = []
        return unit

    def _make_target(self, uid="target-1"):
        class _Target:
            def __init__(self, _id):
                self._id = _id

            def get_attached_unit_root(self):
                return self

        return _Target(uid)

    def test_thrill_seekers_blocks_engaged_target(self):
        unit = self._make_unit(advanced=True, engaged_ids={"target-1"})
        target = self._make_target("target-1")
        game = SimpleNamespace(phase_targeted_units={})
        reason = Unit._thrill_seekers_restriction_reason(unit, target, game)
        self.assertIn("engaged at start of turn", reason)

    def test_thrill_seekers_blocks_already_targeted(self):
        unit = self._make_unit(advanced=True)
        target = self._make_target("target-1")
        game = SimpleNamespace(phase_targeted_units={"target-1": {"other-unit"}})
        reason = Unit._thrill_seekers_restriction_reason(unit, target, game)
        self.assertIn("target already selected", reason)

    def test_thrill_seekers_inactive_without_advance_or_fallback(self):
        unit = self._make_unit(advanced=False, fell_back=False, engaged_ids={"target-1"})
        target = self._make_target("target-1")
        game = SimpleNamespace(phase_targeted_units={"target-1": {"other-unit"}})
        reason = Unit._thrill_seekers_restriction_reason(unit, target, game)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
