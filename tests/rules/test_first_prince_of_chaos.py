import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class TestFirstPrinceOfChaos(unittest.TestCase):
    def _make_unit(self, army, keywords):
        unit = Unit.__new__(Unit)
        unit.parent_army = army
        unit.name = "Test Unit"
        unit.keywords = list(keywords)
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.models = []
        unit.round_state = SimpleNamespace()
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit._ability_cache = {}
        return unit

    def test_khorne_shadow_legion_advances_and_charges(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        unit = self._make_unit(army, ["KHORNE"])

        self.assertTrue(unit.has_advance_and_shoot())
        self.assertTrue(unit.has_advance_and_charge())

    def test_shadow_legion_deep_strike_requires_undivided(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"

        non_undivided = self._make_unit(army, ["HERETIC ASTARTES", "KHORNE"])
        self.assertFalse(non_undivided.has_deep_strike())

        undivided = self._make_unit(army, ["HERETIC ASTARTES", "UNIDIVIDED"])
        self.assertTrue(undivided.has_deep_strike())


if __name__ == "__main__":
    unittest.main()
