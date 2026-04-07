import unittest

from warhammer40k_ai.engine.decision_requests import build_support_artillery_attachment_requests
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.id = name
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


def _make_army(units):
    army = Army.with_detachment(faction="Astra Militarum", detachment_type="Test", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in army.units:
        unit.parent_army = army
    return army


def _loyal_protector_ability(*, with_enhancement_restriction: bool = False) -> Ability:
    tail = "This model cannot be selected as your WARLORD."
    if with_enhancement_restriction:
        tail = "This model cannot be selected as your WARLORD and cannot be given Enhancements."
    return Ability(
        "LOYAL PROTECTOR",
        "",
        (
            "At the start of the Declare Battle Formations step, this model must join one Command Squad unit from your army "
            "(a COMMAND SQUAD cannot have more than one Loyal Protector model joined to it). "
            "This model then counts as part of that COMMAND SQUAD for the rest of the battle, and its Starting Strength is increased accordingly. "
            "If it is not possible to join this model to a COMMAND SQUAD, it does not take part in the battle and counts as having been destroyed. "
            "While this model is joined to a unit, it can embark within any Transport that unit can embark within, and takes up the space of 3 models. "
            + tail
        ),
        "",
        "",
    )


class TestLoyalProtectorAttachment(unittest.TestCase):
    def test_loyal_protector_can_only_join_command_squad(self):
        loyal = _TestUnit(_DummyDatasheet("Nork Deddog", "LP1", abilities=[_loyal_protector_ability()]))
        command_squad = _TestUnit(_DummyDatasheet("Cadian Command Squad", "CS1", keywords=["Infantry"]))
        infantry = _TestUnit(_DummyDatasheet("Infantry Squad", "IS1", keywords=["Infantry"]))
        _make_army([loyal, command_squad, infantry])

        self.assertTrue(loyal.has_joined_support_ability())
        self.assertTrue(loyal.can_join_support_artillery(command_squad))
        self.assertFalse(loyal.can_join_support_artillery(infantry))

    def test_loyal_protector_request_has_no_unattached_option(self):
        loyal = _TestUnit(_DummyDatasheet("Ogryn Bodyguard", "LP1", abilities=[_loyal_protector_ability()]))
        command_squad = _TestUnit(_DummyDatasheet("Krieg Command Squad", "CS1", keywords=["Infantry"]))
        _make_army([loyal, command_squad])

        requests = build_support_artillery_attachment_requests(
            object(),
            [loyal, command_squad],
            queue_requests=False,
        )
        self.assertEqual(1, len(requests))
        labels = [opt.label for opt in list(requests[0].options or [])]
        self.assertNotIn("Unattached", labels)
        self.assertIn(command_squad.name, labels)

    def test_loyal_protector_requires_attachment_when_eligible(self):
        loyal = _TestUnit(_DummyDatasheet("Nork Deddog", "LP1", abilities=[_loyal_protector_ability()]))
        command_squad = _TestUnit(_DummyDatasheet("Catachan Command Squad", "CS1", keywords=["Infantry"]))
        army = _make_army([loyal, command_squad])

        with self.assertRaises(ArmyValidationError):
            army.validate_support_artillery()

        loyal.attach_support_artillery_to(command_squad)
        army.validate_support_artillery()

    def test_loyal_protector_is_removed_when_no_command_squad_exists(self):
        loyal = _TestUnit(_DummyDatasheet("Ogryn Bodyguard", "LP1", abilities=[_loyal_protector_ability()]))
        infantry = _TestUnit(_DummyDatasheet("Infantry Squad", "IS1", keywords=["Infantry"]))
        army = _make_army([loyal, infantry])

        army.validate_support_artillery()

        self.assertNotIn(loyal, army.units)
        self.assertTrue(loyal.special_rules.get("destroyed_before_battle"))

    def test_loyal_protector_joined_unit_can_embark_and_counts_as_three_slots(self):
        loyal = _TestUnit(_DummyDatasheet("Nork Deddog", "LP1", abilities=[_loyal_protector_ability()]))
        command_squad = _TestUnit(_DummyDatasheet("Cadian Command Squad", "CS1", keywords=["Infantry"]))
        transport = _TestUnit(_DummyDatasheet("Chimera", "TR1", keywords=["Transport"]))
        transport.transport_required_keywords = set()
        transport.transport_excluded_keywords = set()
        _make_army([loyal, command_squad, transport])

        loyal.attach_support_artillery_to(command_squad)
        expected_slots = len(command_squad.models) + 3

        self.assertFalse(command_squad.cannot_embark())
        self.assertEqual(expected_slots, command_squad.get_transport_slots_required())

        transport.transport_capacity = expected_slots - 1
        self.assertFalse(transport.can_transport(command_squad))
        transport.transport_capacity = expected_slots
        self.assertTrue(transport.can_transport(command_squad))

    def test_loyal_protector_text_variants_parse_warlord_and_enhancement_restrictions(self):
        variant_one = _TestUnit(_DummyDatasheet("Nork Deddog", "LP1", abilities=[_loyal_protector_ability()]))
        variant_two = _TestUnit(
            _DummyDatasheet(
                "Ogryn Bodyguard",
                "LP2",
                abilities=[_loyal_protector_ability(with_enhancement_restriction=True)],
            )
        )
        _make_army([variant_one, variant_two])

        self.assertTrue(variant_one.special_rules.get("cannot_be_warlord"))
        self.assertFalse(variant_one.special_rules.get("cannot_be_given_enhancements", False))
        self.assertTrue(variant_two.special_rules.get("cannot_be_warlord"))
        self.assertTrue(variant_two.special_rules.get("cannot_be_given_enhancements"))


if __name__ == "__main__":
    unittest.main()
