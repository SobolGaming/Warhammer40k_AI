import unittest

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.game = None


class _DummyDatasheet:
    def __init__(self, name: str, datasheet_id: str, *, abilities=None, keywords=None):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "TestFaction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = []
        self.datasheets_models_cost = []
        self.datasheets_wargear = []
        self.datasheets_options = []
        self.datasheets_abilities = []
        self.attached_to = []
        self.attached_to_names = []
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""
        self.abilities_override = list(abilities or [])


class _TestUnit(Unit):
    """Small Unit subclass to avoid needing full Wahapedia composition parsing for tests."""

    def _parse_unit_composition(self, _data):
        return {"TestModel": 1}

    def _create_models(self, datasheet, quantity=None):
        class _M:
            is_alive = True
            wounds = 1
            _base_wounds = 1
            name = "M"
            leadership = 7
            objective_control = 1
            movement = 6
            toughness = 4
            save = 3
            inv_save = None
            _pending_placement = False
        n = 1 if quantity is None else int(quantity)
        return [_M() for _ in range(n)]

    def _parse_models_cost(self, _data):
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, datasheet):
        return list(getattr(datasheet, "abilities_override", []) or [])

    def add_wargear(self):
        return


class TestSupportArtilleryAttachment(unittest.TestCase):
    def _make_army(self, units):
        army = Army.with_detachment(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = list(units)
        for u in army.units:
            u.parent_army = army
        return army

    def test_support_artillery_join_membership(self):
        ability = Ability(
            "SUPPORT ARTILLERY",
            "",
            "At the start of the Declare Battle Formations step, this model can join one Guardian Defenders unit from your army "
            "(a unit cannot have more than one Support Weapon model joined to it).",
            "",
            "",
        )
        support = _TestUnit(_DummyDatasheet("D-cannon Platform", "S1", abilities=[ability]))
        guardian = _TestUnit(_DummyDatasheet("Guardian Defenders", "G1", keywords=["Infantry"]))
        self._make_army([support, guardian])

        self.assertTrue(support.can_join_support_artillery(guardian))
        support.attach_support_artillery_to(guardian)
        self.assertIs(support.support_joined_to, guardian)
        self.assertIn(support, guardian.attached_support_units)
        self.assertIn(support, guardian.get_attached_unit_members())

    def test_support_artillery_one_per_guardian(self):
        ability = Ability(
            "SUPPORT ARTILLERY",
            "",
            "At the start of the Declare Battle Formations step, this model can join one Guardian Defenders unit from your army "
            "(a unit cannot have more than one Support Weapon model joined to it).",
            "",
            "",
        )
        support1 = _TestUnit(_DummyDatasheet("D-cannon Platform", "S1", abilities=[ability]))
        support2 = _TestUnit(_DummyDatasheet("Vibro Cannon Platform", "S2", abilities=[ability]))
        guardian = _TestUnit(_DummyDatasheet("Guardian Defenders", "G1", keywords=["Infantry"]))
        self._make_army([support1, support2, guardian])

        support1.attach_support_artillery_to(guardian)
        self.assertFalse(support2.can_join_support_artillery(guardian))

    def test_support_artillery_in_wound_allocation(self):
        ability = Ability(
            "SUPPORT ARTILLERY",
            "",
            "At the start of the Declare Battle Formations step, this model can join one Guardian Defenders unit from your army "
            "(a unit cannot have more than one Support Weapon model joined to it).",
            "",
            "",
        )
        support = _TestUnit(_DummyDatasheet("Shadow Weaver Platform", "S1", abilities=[ability]))
        guardian = _TestUnit(_DummyDatasheet("Guardian Defenders", "G1", keywords=["Infantry"]))
        self._make_army([support, guardian])
        support.attach_support_artillery_to(guardian)

        support_model = support.models[0]
        candidates = guardian.get_models_for_wound_allocation()
        self.assertIn(support_model, candidates)

    def test_joined_guardian_cannot_embark(self):
        ability = Ability(
            "SUPPORT ARTILLERY",
            "",
            "At the start of the Declare Battle Formations step, this model can join one Guardian Defenders unit from your army "
            "(a unit cannot have more than one Support Weapon model joined to it).",
            "",
            "",
        )
        support = _TestUnit(_DummyDatasheet("D-cannon Platform", "S1", abilities=[ability]))
        guardian = _TestUnit(_DummyDatasheet("Guardian Defenders", "G1", keywords=["Infantry"]))
        transport = _TestUnit(_DummyDatasheet("Wave Serpent", "T1", keywords=["Transport"]))
        transport.transport_capacity = 10
        transport.transport_required_keywords = set()
        transport.transport_excluded_keywords = set()

        self._make_army([support, guardian, transport])

        # Guardian can embark before joining
        self.assertTrue(transport.can_transport(guardian))

        support.attach_support_artillery_to(guardian)
        self.assertTrue(guardian.cannot_embark())
        self.assertFalse(transport.can_transport(guardian))


if __name__ == "__main__":
    unittest.main()
