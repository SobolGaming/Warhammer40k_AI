import unittest

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.game = None


class _DummyDatasheet:
    def __init__(self, name: str, datasheet_id: str, attached_to=None, *, attached_to_names=None, keywords=None):
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
        self.attached_to = attached_to or []
        self.attached_to_names = attached_to_names or []
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""


class _TestUnit(Unit):
    """Small Unit subclass to avoid needing full Wahapedia composition parsing for tests."""

    def _parse_unit_composition(self, _data):
        # minimal: one model
        return {"TestModel": 1}

    def _create_models(self, datasheet, quantity=None):
        # avoid importing Model; we only need len(models) for get_unit_cost in these tests
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
            has_circular_base = True
        n = 1 if quantity is None else int(quantity)
        return [_M() for _ in range(n)]

    def _parse_models_cost(self, _data):
        # fixed points regardless of model count here
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, _datasheet):
        return []

    def add_wargear(self):
        return


class TestLeaderAttachments(unittest.TestCase):
    def test_leader_can_attach_to_multiple_types_but_only_one_target(self):
        # Leader can attach to BG1 or BG2 by datasheet id
        leader_ds = _DummyDatasheet("Leader", "L1", attached_to=["B1", "B2"])
        bg1_ds = _DummyDatasheet("Bodyguard1", "B1")
        bg2_ds = _DummyDatasheet("Bodyguard2", "B2")

        leader = _TestUnit(leader_ds)
        bg1 = _TestUnit(bg1_ds)
        bg2 = _TestUnit(bg2_ds)

        # Fake army wiring for same-army constraint
        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bg1, bg2]
        for u in army.units:
            u.parent_army = army

        self.assertTrue(leader.can_attach_to(bg1))
        self.assertTrue(leader.can_attach_to(bg2))

        leader.attach_to_unit(bg1)
        self.assertIs(leader.attached_to, bg1)
        self.assertIn(leader, bg1.attached_leaders)

        # attaching to a different valid unit should detach from prior
        leader.attach_to_unit(bg2)
        self.assertIs(leader.attached_to, bg2)
        self.assertNotIn(leader, bg1.attached_leaders)
        self.assertIn(leader, bg2.attached_leaders)

    def test_army_validate_leaders_allows_unattached_and_enforces_limit(self):
        leader_ds = _DummyDatasheet("Leader", "L1", attached_to=["B1"])
        bg_ds = _DummyDatasheet("Bodyguard", "B1")
        leader = _TestUnit(leader_ds)
        bg = _TestUnit(bg_ds)

        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bg]
        for u in army.units:
            u.parent_army = army

        # Unattached leader is OK
        army.validate_leaders()

        # Attach and validate OK
        leader.attach_to_unit(bg)
        army.validate_leaders()

    def test_attached_unit_uses_best_leadership_lowest_value(self):
        leader_ds = _DummyDatasheet("Leader", "L1", attached_to=["B1"])
        bg_ds = _DummyDatasheet("Bodyguard", "B1")
        leader = _TestUnit(leader_ds)
        bg = _TestUnit(bg_ds, quantity=5)

        # Make leader better (lower) Leadership
        for m in leader.models:
            m.leadership = 5
        for m in bg.models:
            m.leadership = 7

        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bg]
        for u in army.units:
            u.parent_army = army

        leader.attach_to_unit(bg)
        self.assertEqual(bg.leadership, 5)
        # attached leader delegates
        self.assertEqual(leader.leadership, 5)

    def test_attached_unit_below_half_strength_uses_combined_starting_strength(self):
        leader_ds = _DummyDatasheet("Leader", "L1", attached_to=["B1"])
        bg_ds = _DummyDatasheet("Bodyguard", "B1")
        leader = _TestUnit(leader_ds)         # 1 model
        bg = _TestUnit(bg_ds, quantity=5)     # 5 models

        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bg]
        for u in army.units:
            u.parent_army = army

        leader.attach_to_unit(bg)

        # Starting strength 6; current 6 -> not below half
        self.assertFalse(bg.is_below_half_strength())

        # Kill 4 bodyguards -> current models = 2 (1 leader + 1 bodyguard) which is below half of 6
        bg.models = bg.models[:1]
        self.assertTrue(bg.is_below_half_strength())

        # Attached leader should not be evaluated separately (avoid double-testing)
        self.assertFalse(leader.is_below_half_strength())

    def test_leader_death_detaches_from_bodyguard(self):
        leader_ds = _DummyDatasheet("Leader", "L1", attached_to=["B1"])
        bg_ds = _DummyDatasheet("Bodyguard", "B1")
        leader = _TestUnit(leader_ds)
        bg = _TestUnit(bg_ds, quantity=3)

        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bg]
        for u in army.units:
            u.parent_army = army

        leader.attach_to_unit(bg)
        self.assertIn(leader, bg.attached_leaders)

        # Simulate leader destroyed (remove last model)
        last = leader.models[0]
        leader.remove_model(last, fleed=False, game_map=None)

        self.assertIsNone(getattr(leader, "attached_to", None))
        self.assertNotIn(leader, bg.attached_leaders)

    def test_attached_unit_rule_allows_attachment(self):
        leader_ds = _DummyDatasheet(
            "Leader",
            "L1",
            attached_to=["BASE"],
            attached_to_names=["Base Unit"],
            keywords=["CAPTAIN", "CHARACTER"],
        )
        bodyguard_ds = _DummyDatasheet("Bodyguard", "BG1")
        leader = _TestUnit(leader_ds)
        bodyguard = _TestUnit(bodyguard_ds)

        bodyguard.possible_abilities = [
            Ability(
                "Attached Unit",
                "",
                "If a CAPTAIN model from your army with the Leader ability can be attached to a Base Unit unit, it can be attached to this unit instead.",
                "",
            )
        ]

        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bodyguard]
        for u in army.units:
            u.parent_army = army

        self.assertTrue(leader.can_attach_to(bodyguard))

    def test_attached_unit_rule_requires_keyword(self):
        leader_ds = _DummyDatasheet(
            "Leader",
            "L1",
            attached_to=["BASE"],
            attached_to_names=["Base Unit"],
            keywords=["LIEUTENANT"],
        )
        bodyguard_ds = _DummyDatasheet("Bodyguard", "BG1")
        leader = _TestUnit(leader_ds)
        bodyguard = _TestUnit(bodyguard_ds)

        bodyguard.possible_abilities = [
            Ability(
                "Attached Unit",
                "",
                "If a CAPTAIN model from your army with the Leader ability can be attached to a Base Unit unit, it can be attached to this unit instead.",
                "",
            )
        ]

        army = Army(faction="Test", detachment_type="Test", points_limit=2000)
        army.player = _DummyPlayer()
        army.units = [leader, bodyguard]
        for u in army.units:
            u.parent_army = army

        self.assertFalse(leader.can_attach_to(bodyguard))


if __name__ == "__main__":
    unittest.main()

