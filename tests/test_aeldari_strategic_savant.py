import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class TestAeldariStrategicSavant(unittest.TestCase):
    def _make_unit(self, army, *, name, keywords):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = list(keywords or [])
        unit.faction_keywords = ["Aeldari"]
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.possible_abilities = []
        return unit

    def test_strategic_savant_adds_objective_control(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Aeldari", detachment_type="Aspect Host")
        army.faction_id = "AE"

        bodyguard = self._make_unit(army, name="Dire Avengers", keywords=["Aspect Warriors"])
        model = SimpleNamespace(is_alive=True, objective_control=2, _objective_control=2)
        bodyguard.models = [model]

        leader = self._make_unit(army, name="Autarch", keywords=["Character"])
        leader.special_rules = {"enhancement_strategic_savant": True}
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        oc = bodyguard.get_effective_model_characteristic(model, "objective_control")
        self.assertEqual(oc, 3)


if __name__ == "__main__":
    unittest.main()
