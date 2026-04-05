import unittest

from warhammer40k_ai.engine.decision_requests import build_support_artillery_attachment_requests
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.id = name
        self.game = None


class _DummyDatasheet:
    def __init__(self, name: str, datasheet_id: str, *, abilities=None, keywords=None, attached_to=None):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = []
        self.datasheets_models_cost = []
        self.datasheets_wargear = []
        self.datasheets_options = []
        self.datasheets_abilities = []
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""
        self.abilities_override = list(abilities or [])


class _TestUnit(Unit):
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
            abilities = []
            wargear = []
            optional_wargear = []
            keywords = []
            faction_keywords = []

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


def _masters_of_the_maelstrom_ability() -> Ability:
    return Ability(
        "MASTERS OF THE MAELSTROM",
        "",
        (
            "At the start of the Declare Battle Formations step, this unit can join one of the following units. "
            "This unit then counts as part of that unit for the rest of the battle, and that unit's Starting Strength "
            "is increased accordingly. Chosen, Legionaries, Red Corsairs Raiders. This unit cannot join an Attached unit, "
            "and only Huron Blackheart can join a unit this unit has joined."
        ),
        "",
        "",
    )


def _make_army(units):
    army = Army(faction="CSM", detachment_type="Renegade Raiders", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in army.units:
        unit.parent_army = army
    return army


class TestMastersOfTheMaelstromAttachment(unittest.TestCase):
    def test_masters_of_the_maelstrom_targets_only_supported_units(self):
        support = _TestUnit(_DummyDatasheet("Masters of the Maelstrom", "MOTM1", abilities=[_masters_of_the_maelstrom_ability()]))
        chosen = _TestUnit(_DummyDatasheet("Chosen", "BG1", keywords=["Infantry"]))
        legionaries = _TestUnit(_DummyDatasheet("Legionaries", "BG2", keywords=["Infantry"]))
        raiders = _TestUnit(_DummyDatasheet("Red Corsairs Raiders", "BG3", keywords=["Infantry"]))
        havocs = _TestUnit(_DummyDatasheet("Havocs", "BG4", keywords=["Infantry"]))
        _make_army([support, chosen, legionaries, raiders, havocs])

        self.assertTrue(support.has_joined_support_ability())
        self.assertEqual("masters_of_the_maelstrom", support._joined_support_rule_kind())
        self.assertTrue(support.can_join_support_artillery(chosen))
        self.assertTrue(support.can_join_support_artillery(legionaries))
        self.assertTrue(support.can_join_support_artillery(raiders))
        self.assertFalse(support.can_join_support_artillery(havocs))

    def test_masters_of_the_maelstrom_cannot_join_attached_unit(self):
        support = _TestUnit(_DummyDatasheet("Masters of the Maelstrom", "MOTM1", abilities=[_masters_of_the_maelstrom_ability()]))
        legionaries = _TestUnit(_DummyDatasheet("Legionaries", "LEG1", keywords=["Infantry"]))
        non_huron_leader = _TestUnit(
            _DummyDatasheet(
                "Chaos Lord",
                "LEAD1",
                keywords=["Character", "Infantry"],
                attached_to=["LEG1"],
            )
        )
        _make_army([support, legionaries, non_huron_leader])

        non_huron_leader.attach_to_unit(legionaries)
        self.assertFalse(support.can_join_support_artillery(legionaries))

    def test_masters_of_the_maelstrom_request_options_include_unattached_and_eligible_targets(self):
        support = _TestUnit(_DummyDatasheet("Masters of the Maelstrom", "MOTM1", abilities=[_masters_of_the_maelstrom_ability()]))
        chosen = _TestUnit(_DummyDatasheet("Chosen", "BG1", keywords=["Infantry"]))
        legionaries = _TestUnit(_DummyDatasheet("Legionaries", "BG2", keywords=["Infantry"]))
        raiders = _TestUnit(_DummyDatasheet("Red Corsairs Raiders", "BG3", keywords=["Infantry"]))
        havocs = _TestUnit(_DummyDatasheet("Havocs", "BG4", keywords=["Infantry"]))
        units = [support, chosen, legionaries, raiders, havocs]
        _make_army(units)

        requests = build_support_artillery_attachment_requests(object(), units, queue_requests=False)
        self.assertEqual(1, len(requests))
        labels = [opt.label for opt in list(requests[0].options or [])]
        self.assertIn("Unattached", labels)
        self.assertIn("Chosen", labels)
        self.assertIn("Legionaries", labels)
        self.assertIn("Red Corsairs Raiders", labels)
        self.assertNotIn("Havocs", labels)

    def test_only_huron_blackheart_can_join_unit_after_masters_of_the_maelstrom_join(self):
        support = _TestUnit(_DummyDatasheet("Masters of the Maelstrom", "MOTM1", abilities=[_masters_of_the_maelstrom_ability()]))
        legionaries = _TestUnit(_DummyDatasheet("Legionaries", "LEG1", keywords=["Infantry"]))
        huron = _TestUnit(
            _DummyDatasheet(
                "Huron Blackheart",
                "000000925",
                keywords=["Character", "Infantry"],
                attached_to=["LEG1"],
            )
        )
        non_huron_leader = _TestUnit(
            _DummyDatasheet(
                "Chaos Lord",
                "LEAD1",
                keywords=["Character", "Infantry"],
                attached_to=["LEG1"],
            )
        )
        _make_army([support, legionaries, huron, non_huron_leader])

        support.attach_support_artillery_to(legionaries)

        self.assertFalse(non_huron_leader.can_attach_to(legionaries))
        with self.assertRaises(ValueError):
            non_huron_leader.attach_to_unit(legionaries)

        self.assertTrue(huron.can_attach_to(legionaries))
        huron.attach_to_unit(legionaries)
        self.assertIs(huron.attached_to, legionaries)


if __name__ == "__main__":
    unittest.main()
